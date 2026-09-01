"""Builds the vault-wide link graph: backlinks, outgoing links, and the tag map."""

import os
import re
from dataclasses import dataclass, field

from .frontmatter import split_frontmatter
from .links import parse_embed, parse_wikilink
from .markdown import strip_block_comments, strip_html_comments
from .resolver import resolve_embed, resolve_note
from .search import SearchIndex
from .vault import Vault

# A hostile note repeating one link endlessly would otherwise grow the mention
# list without bound; past this many mentions of a target, the rest are dropped.
MAX_MENTIONS_PER_TARGET = int(os.environ.get("READER_MAX_MENTIONS_PER_TARGET", "1000"))

CONTEXT_RADIUS = 80

_WIKILINK = re.compile(r"!?\[\[([^\[\]\n]+?)\]\]")
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_FENCE_LINE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_TAG = re.compile(r"(?:^|(?<=[ \t(\[{'\"“‘>,;:]))#([\w/-]+)")
_TAG_BODY = re.compile(r"[\w/-]+")


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
        """Reads every note once and records its links and tags."""
        graph = cls()
        total = len(vault.notes)
        for position, rel in enumerate(vault.notes):
            note = vault.read_note(rel)
            if not note.error:
                graph.add(vault, rel, note.text)
            if progress is not None:
                progress(position + 1, total)
        graph.ready = True
        return graph

    def add(self, vault: Vault, rel: str, text: str) -> None:
        """Indexes one note's wikilinks and tags into the graph."""
        split = split_frontmatter(text)
        for tag in _frontmatter_tags(split.properties):
            self._add_tag(rel, tag)
        body = strip_html_comments(strip_block_comments(split.body))
        outgoing: list[Outgoing] = []
        seen_out: set[tuple[str, str]] = set()
        for line in _content_lines(body):
            plain = _INLINE_CODE.sub("", line)
            for match in _WIKILINK.finditer(plain):
                embed = match.group(0).startswith("!")
                link = parse_embed(match.group(1)) if embed else parse_wikilink(match.group(1))
                if not link.target:
                    continue
                resolve = resolve_embed if embed else resolve_note
                resolved = resolve(vault, rel, link.target)
                # A media embed is an attachment, not a note link; it stays out
                # of the graph so the outgoing panel lists notes and failures only.
                if embed and resolved.kind not in ("note", "ambiguous", "missing"):
                    continue
                out = Outgoing(link.target, resolved.path, resolved.kind)
                if (out.target, out.path) not in seen_out:
                    seen_out.add((out.target, out.path))
                    outgoing.append(out)
                if resolved.kind == "note" and resolved.path != rel:
                    self._add_mention(resolved.path, rel, plain, match.start())
            for match in _TAG.finditer(_WIKILINK.sub(" ", plain)):
                self._add_tag(rel, match.group(1))
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

    def _add_mention(self, target: str, source: str, line: str, position: int) -> None:
        mentions = self.backlinks.setdefault(target, [])
        if len(mentions) >= MAX_MENTIONS_PER_TARGET:
            return
        mentions.append(Mention(source=source, context=_context(line, position)))

    def _add_tag(self, rel: str, tag: str) -> None:
        tag = tag.lstrip("#").strip()
        if not _TAG_BODY.fullmatch(tag) or _is_numeric_tag(tag):
            return
        folded = tag.casefold()
        note_set = self.note_tags.setdefault(rel, set())
        if folded in note_set:
            return
        note_set.add(folded)
        self.tags.setdefault(folded, []).append(rel)
        self.tag_names.setdefault(folded, tag)


def build_indexes(vault: Vault, progress=None) -> tuple[SearchIndex, VaultGraph]:
    """Builds the search index and the link graph in one pass over the notes."""
    index = SearchIndex()
    graph = VaultGraph()
    total = len(vault.notes)
    for position, rel in enumerate(vault.notes):
        note = vault.read_note(rel)
        if not note.error:
            index.add(rel, note.text)
            graph.add(vault, rel, note.text)
        if progress is not None:
            progress(position + 1, total)
    index.ready = True
    graph.ready = True
    return index, graph


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


def _frontmatter_tags(properties: dict):
    """Yields the tag strings out of a `tags` or `tag` frontmatter property."""
    for key in ("tags", "tag"):
        value = properties.get(key)
        if isinstance(value, str):
            yield from re.split(r"[,\s]+", value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    yield item


def _is_numeric_tag(tag: str) -> bool:
    return tag.replace("/", "").replace("-", "").replace("_", "").isdigit()


def _context(line: str, position: int) -> str:
    start = max(0, position - CONTEXT_RADIUS)
    end = min(len(line), position + CONTEXT_RADIUS)
    fragment = re.sub(r"\s+", " ", line[start:end]).strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(line) else ""
    return f"{prefix}{fragment}{suffix}"
