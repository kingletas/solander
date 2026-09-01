"""Scans notes for links and tags, and assembles the vault-wide graph from the scans.

The split is what makes the index incremental: `scan_note` is pure and cacheable
per note, while `VaultGraph.assemble` resolves every cached scan against the
current file index — cheap enough to redo whenever the vault changes.
"""

import os
import re
from dataclasses import dataclass, field

from .frontmatter import split_frontmatter
from .links import parse_embed, parse_wikilink
from .markdown import strip_block_comments, strip_html_comments
from .resolver import resolve_embed, resolve_note
from .vault import Vault

# A hostile note repeating one link endlessly would otherwise grow the mention
# list without bound; past this many mentions of a target, the rest are dropped.
MAX_MENTIONS_PER_TARGET = int(os.environ.get("READER_MAX_MENTIONS_PER_TARGET", "1000"))
MAX_LINKS_PER_NOTE = int(os.environ.get("READER_MAX_LINKS_PER_NOTE", "2000"))

CONTEXT_RADIUS = 80

_WIKILINK = re.compile(r"!?\[\[([^\[\]\n]+?)\]\]")
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_FENCE_LINE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_TAG = re.compile(r"(?:^|(?<=[ \t(\[{'\"“‘>,;:]))#([\w/-]+)")
_TAG_BODY = re.compile(r"[\w/-]+")


@dataclass(frozen=True)
class RawLink:
    """One wikilink or embed as written: its target, kind, and surrounding line."""

    target: str
    embed: bool = False
    context: str = ""


@dataclass(frozen=True)
class NoteScan:
    """Everything the graph needs from one note, independent of the rest of the vault."""

    links: tuple[RawLink, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Mention:
    """One place a note is linked from: the source note and the line around the link."""

    source: str
    context: str


@dataclass(frozen=True)
class Outgoing:
    """One link out of a note: the written target, its resolved path, and how it resolved."""

    target: str
    path: str = ""
    kind: str = "note"


def scan_note(text: str) -> NoteScan:
    """Extracts a note's wikilinks (with context) and tags, touching no other note.

    Links and tags inside fenced code, inline code, and comments do not count,
    and a media embed is classified later, at resolution time.
    """
    # A full YAML parse per note measured as 60% of the whole build on a
    # 10k-note vault, so the bulk pass reads the tag keys out of the raw block.
    split = split_frontmatter(text, parse_properties=False)
    tags: list[str] = []
    seen_tags: set[str] = set()
    for tag in _frontmatter_tags(split.raw_frontmatter):
        _collect_tag(tag, tags, seen_tags)
    links: list[RawLink] = []
    body = strip_html_comments(strip_block_comments(split.body))
    for line in _content_lines(body):
        has_link = "[[" in line
        has_tag = "#" in line
        if not has_link and not has_tag:
            continue
        plain = _INLINE_CODE.sub("", line) if "`" in line else line
        for match in _WIKILINK.finditer(plain) if has_link else ():
            embed = match.group(0).startswith("!")
            link = parse_embed(match.group(1)) if embed else parse_wikilink(match.group(1))
            if not link.target or len(links) >= MAX_LINKS_PER_NOTE:
                continue
            links.append(RawLink(link.target, embed, _context(plain, match.start())))
        if has_tag:
            source = _WIKILINK.sub(" ", plain) if has_link else plain
            for match in _TAG.finditer(source):
                _collect_tag(match.group(1), tags, seen_tags)
    return NoteScan(links=tuple(links), tags=tuple(tags))


@dataclass
class VaultGraph:
    """Backlinks, outgoing links, and tags for every note, built without writing anything."""

    backlinks: dict[str, list[Mention]] = field(default_factory=dict)
    outgoing: dict[str, list[Outgoing]] = field(default_factory=dict)
    tags: dict[str, list[str]] = field(default_factory=dict)
    tag_names: dict[str, str] = field(default_factory=dict)
    note_tags: dict[str, set[str]] = field(default_factory=dict)
    ready: bool = False

    @classmethod
    def build(cls, vault: Vault, progress=None) -> "VaultGraph":
        """Reads and scans every note, then assembles the graph — the from-scratch path."""
        scans: dict[str, NoteScan] = {}
        total = len(vault.notes)
        for position, rel in enumerate(vault.notes):
            note = vault.read_note(rel)
            if not note.error:
                scans[rel] = scan_note(note.text)
            if progress is not None:
                progress(position + 1, total)
        return cls.assemble(vault, scans)

    @classmethod
    def assemble(cls, vault: Vault, scans: dict[str, NoteScan]) -> "VaultGraph":
        """Resolves every scan against the current index into the vault-wide graph."""
        graph = cls()
        exists = _index_membership(vault)
        for rel in vault.notes:
            scan = scans.get(rel)
            if scan is not None:
                graph._add_scan(vault, rel, scan, exists)
        graph.ready = True
        return graph

    def _add_scan(self, vault: Vault, rel: str, scan: NoteScan, exists) -> None:
        for tag in scan.tags:
            self._add_tag(rel, tag)
        outgoing: list[Outgoing] = []
        seen_out: set[tuple[str, str]] = set()
        for raw in scan.links:
            resolve = resolve_embed if raw.embed else resolve_note
            resolved = resolve(vault, rel, raw.target, exists)
            # A media embed is an attachment, not a note link; it stays out of
            # the graph so the outgoing panel lists notes and failures only.
            if raw.embed and resolved.kind not in ("note", "ambiguous", "missing"):
                continue
            out = Outgoing(raw.target, resolved.path, resolved.kind)
            if (out.target, out.path) not in seen_out:
                seen_out.add((out.target, out.path))
                outgoing.append(out)
            if resolved.kind == "note" and resolved.path != rel:
                self._add_mention(resolved.path, rel, raw.context)
        if outgoing:
            self.outgoing[rel] = outgoing

    def notes_tagged(self, tag: str) -> list[str]:
        """Returns the notes carrying a tag, nested children included."""
        folded = tag.casefold()
        collected: list[str] = []
        for key, notes in self.tags.items():
            if key == folded or key.startswith(f"{folded}/"):
                collected.extend(notes)
        return sorted(set(collected))

    def _add_mention(self, target: str, source: str, context: str) -> None:
        mentions = self.backlinks.setdefault(target, [])
        if len(mentions) >= MAX_MENTIONS_PER_TARGET:
            return
        mentions.append(Mention(source=source, context=context))

    def _add_tag(self, rel: str, tag: str) -> None:
        folded = tag.casefold()
        note_set = self.note_tags.setdefault(rel, set())
        if folded in note_set:
            return
        note_set.add(folded)
        self.tags.setdefault(folded, []).append(rel)
        self.tag_names.setdefault(folded, tag)


def local_neighbors(graph: "VaultGraph", rel: str, cap: int = 30) -> list[tuple[str, str]]:
    """Returns a note's neighbors as (path, direction): 'in', 'out', or 'both'.

    Bidirectional links come first, then backlinks, then outgoing, capped so a
    hub note draws a legible ring instead of a starburst.
    """
    incoming = {mention.source for mention in graph.backlinks.get(rel, [])}
    outgoing = {
        link.path for link in graph.outgoing.get(rel, []) if link.kind == "note" and link.path
    }
    outgoing.discard(rel)
    incoming.discard(rel)
    both = incoming & outgoing
    ordered = [(path, "both") for path in sorted(both)]
    ordered += [(path, "in") for path in sorted(incoming - both)]
    ordered += [(path, "out") for path in sorted(outgoing - both)]
    return ordered[:cap]


def _collect_tag(tag: str, tags: list[str], seen: set[str]) -> None:
    tag = tag.lstrip("#").strip()
    if not _TAG_BODY.fullmatch(tag) or _is_numeric_tag(tag):
        return
    folded = tag.casefold()
    if folded not in seen:
        seen.add(folded)
        tags.append(tag)


def _index_membership(vault: Vault):
    """Returns an existence predicate over the vault's indexed files."""
    known = set(vault.files)
    return known.__contains__


def _content_lines(body: str):
    """Yields the lines of a body that sit outside fenced code blocks."""
    fence = ""
    for line in body.split("\n"):
        match = _FENCE_LINE.match(line)
        if match:
            marker = match.group(1)
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
            continue
        if not fence:
            yield line


_TAG_KEY = re.compile(r"^(?:tags|tag)\s*:\s*(.*)$")
_TAG_ITEM = re.compile(r"^\s*-\s+(.+)$")


def _frontmatter_tags(raw: str):
    """Yields tag strings from a raw frontmatter block without a YAML parse.

    Reads the shapes a vault actually writes — an inline value, or a `- item`
    block list (indented or not, blank lines allowed) under a top-level
    `tags:`/`tag:` key; anything more exotic yields nothing.
    """
    lines = raw.split("\n")
    index = 0
    while index < len(lines):
        match = _TAG_KEY.match(lines[index])
        index += 1
        if not match:
            continue
        value = match.group(1).split(" #")[0].strip()
        if value:
            yield from (item.strip("\"'[] ") for item in re.split(r"[,\s]+", value))
            continue
        while index < len(lines):
            if not lines[index].strip():
                index += 1
                continue
            item = _TAG_ITEM.match(lines[index])
            if not item:
                break
            yield item.group(1).split(" #")[0].strip("\"' ")
            index += 1


def _is_numeric_tag(tag: str) -> bool:
    return tag.replace("/", "").replace("-", "").replace("_", "").isdigit()


def _context(line: str, position: int) -> str:
    start = max(0, position - CONTEXT_RADIUS)
    end = min(len(line), position + CONTEXT_RADIUS)
    fragment = re.sub(r"\s+", " ", line[start:end]).strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(line) else ""
    return f"{prefix}{fragment}{suffix}"
