"""Renders a note to a sanitized HTML page: transforms, embeds, highlighting, assembly."""

import html
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from importlib import resources
from urllib.parse import quote, unquote

from latex2mathml.converter import convert as latex_to_mathml
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from .bases import render_base
from .callouts import callouts_rule
from .canvas import canvas_body, parse_canvas
from .dataview import DataviewEngine
from .dql import DqlError
from .excalidraw import excalidraw_body
from .frontmatter import split_frontmatter
from .kanban import kanban_body, parse_kanban
from .links import WikiLink, slugify
from .markdown import build_parser, strip_block_comments, strip_html_comments
from .mindmap import mindmap_body
from .resolver import Resolution, resolve_attachment, resolve_embed, resolve_note
from .sanitize import sanitize
from .vault import Vault

MAX_EMBED_DEPTH = int(os.environ.get("READER_MAX_EMBED_DEPTH", "5"))

# The depth limit alone leaves multiplicative growth open: 8-wide embeds at
# depth 5 measured a 23 MB page in 29 s. The budget caps note embeds per page.
MAX_EMBEDS_PER_PAGE = int(os.environ.get("READER_MAX_EMBEDS_PER_PAGE", "200"))

# A hover preview shows the opening of a note, so it takes a slice of the body
# and a tight embed budget rather than paying for the whole page.
PREVIEW_MAX_CHARS = int(os.environ.get("READER_PREVIEW_MAX_CHARS", "2500"))
PREVIEW_EMBED_BUDGET = 4

# Fence languages that Obsidian executes and this reader deliberately does not.
INERT_FENCES = {"dataviewjs", "templater", "tasks", "query", "meta-bind"}

# TeX past this length is not a formula, and the converter's cost grows with it.
MAX_MATH_CHARS = int(os.environ.get("READER_MAX_MATH_CHARS", "5000"))

# The in-page "On this page" rail and the linked-mentions footer stay readable
# by staying bounded; the sidebar panels carry the full lists.
MAX_TOC_ENTRIES = 40
MAX_FOOTER_BACKLINKS = 50
MAX_HEADER_TAGS = 8
READING_WORDS_PER_MINUTE = 220

_BLOCK_ID_TAIL = re.compile(r"[ \t]+\^[A-Za-z0-9-]+[ \t]*$")
_FENCE_LINE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


@dataclass(frozen=True)
class Heading:
    """One outline entry: level, display text, and the anchor id it renders with."""

    level: int
    text: str
    anchor: str


@dataclass
class RenderedNote:
    """A fully rendered note page and the structure the GUI hangs UI on."""

    page: str = ""
    body: str = ""
    title: str = ""
    outline: list[Heading] = field(default_factory=list)
    properties: dict = field(default_factory=dict)
    source: str = ""
    lossy: bool = False
    error: str = ""


def note_uri(rel: str, anchor: str = "") -> str:
    """Builds the internal `reader:` URI for a vault-relative note path."""
    uri = f"reader:///note/{quote(rel)}"
    return f"{uri}#{quote(anchor)}" if anchor else uri


def vault_uri(rel: str) -> str:
    """Builds the `vault:` URI the asset scheme handler serves a file from."""
    return f"vault:///{quote(rel)}"


def strip_block_ids(text: str) -> str:
    """Removes trailing `^block-id` markers from lines outside fenced code."""
    lines = text.split("\n")
    output = []
    fence = ""
    for line in lines:
        match = _FENCE_LINE.match(line)
        if match:
            marker = match.group(1)
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
            output.append(line)
            continue
        output.append(line if fence else _BLOCK_ID_TAIL.sub("", line))
    return "\n".join(output)


def _find_section(body: str, anchor: str) -> str:
    """Extracts the Markdown of one heading section, matched by normalized anchor."""
    wanted = slugify(anchor.split("#")[-1])
    lines = body.split("\n")
    start = None
    level = 0
    fence = ""
    for index, line in enumerate(lines):
        match = _FENCE_LINE.match(line)
        if match:
            marker = match.group(1)
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
            continue
        if fence:
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if not heading:
            continue
        if start is None:
            if slugify(heading.group(2).strip()) == wanted:
                start = index
                level = len(heading.group(1))
        elif len(heading.group(1)) <= level:
            return "\n".join(lines[start:index])
    return "\n".join(lines[start:]) if start is not None else ""


def _find_block(body: str, block_id: str) -> str:
    """Extracts the paragraph or line carrying a `^block-id` marker."""
    lines = body.split("\n")
    marker = re.compile(rf"(^|\s)\^{re.escape(block_id)}\s*$")
    for index, line in enumerate(lines):
        if not marker.search(line):
            continue
        if line.strip() == f"^{block_id}" and index > 0:
            index -= 1
        start = index
        while start > 0 and lines[start - 1].strip():
            start -= 1
        end = index
        while end + 1 < len(lines) and lines[end + 1].strip():
            end += 1
        return "\n".join(lines[start : end + 1])
    return ""


class NoteRenderer:
    """Renders notes from one vault, resolving links and embeds as it goes."""

    def __init__(self, vault: Vault, typography=None, graph_provider=None, snippets=None):
        self.vault = vault
        self.typography = typography
        self.graph_provider = graph_provider
        self.snippets = snippets
        self.md = build_parser()
        self.md.core.ruler.before("inline", "obsidian_callouts", callouts_rule)
        self._install_render_rules()

    def _typo(self) -> dict | None:
        return self.typography() if callable(self.typography) else None

    def _snips(self) -> str:
        return self.snippets() if callable(self.snippets) else ""

    def render(self, rel: str, theme: str = "light") -> RenderedNote:
        """Renders one note into a complete sanitized page."""
        note = self.vault.read_note(rel)
        title = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        typo = self._typo()
        if note.error:
            return RenderedNote(
                page=build_page(
                    _message_body("Cannot open note", note.error), title, theme, typography=typo
                ),
                title=title,
                error=note.error,
            )
        split = split_frontmatter(note.text)
        env = self._env(rel)
        if isinstance(split.properties, dict) and split.properties.get("excalidraw-plugin"):
            drawing = excalidraw_body(split.body)
            return RenderedNote(
                page=build_page(
                    drawing, title, theme, typography=typo, extra_css=self._snips(),
                    note_classes="excalidraw-note",
                ),
                body=drawing,
                title=title,
                source=note.text,
            )
        if isinstance(split.properties, dict) and split.properties.get("kanban-plugin"):
            board = kanban_body(
                parse_kanban(split.body),
                lambda text: self.md.renderInline(text, env),
            )
            body_html = board
        else:
            body_html = self._render_markdown(split.body, env)
        properties_html = _properties_block(split.properties)
        body = sanitize(properties_html + body_html)
        header = note_header(
            rel, title, split.properties, split.body, env["outline"], self._mtime(rel)
        )
        toc = "" if (typo or {}).get("width") in ("wide", "full") else page_toc(env["outline"])
        footer = self._backlinks_footer(rel)
        return RenderedNote(
            page=build_page(
                header + toc + body + footer,
                title,
                theme,
                lossy=note.lossy,
                typography=typo,
                extra_css=self._snips(),
                note_classes=_css_classes(split.properties),
            ),
            body=body,
            title=title,
            outline=env["outline"],
            properties=split.properties,
            source=note.text,
            lossy=note.lossy,
        )

    def _mtime(self, rel: str) -> float | None:
        try:
            return (self.vault.root / rel).stat().st_mtime
        except OSError:
            return None

    def _backlinks_footer(self, rel: str) -> str:
        """Lists the notes linking here after the content, quietly and collapsed."""
        graph = self._graph()
        if graph is None:
            return ""
        mentions = graph.backlinks.get(rel, [])
        if not mentions:
            return ""
        items = []
        for mention in mentions[:MAX_FOOTER_BACKLINKS]:
            source_title = html.escape(mention.source.rsplit("/", 1)[-1].rsplit(".", 1)[0])
            path = html.escape(mention.source)
            context = html.escape(mention.context or "")
            context_html = f'<div class="backlink-context">{context}</div>' if context else ""
            items.append(
                f'<li><a class="wikilink" href="{note_uri(mention.source)}">{source_title}</a>'
                f'<span class="backlink-path">{path}</span>{context_html}</li>'
            )
        more = ""
        if len(mentions) > MAX_FOOTER_BACKLINKS:
            more = (
                f'<div class="backlink-more">…and {len(mentions) - MAX_FOOTER_BACKLINKS} more '
                "— the Links panel lists them all</div>"
            )
        label = "1 note links here" if len(mentions) == 1 else f"{len(mentions)} notes link here"
        return (
            f'<section class="backlinks"><details><summary>{label}</summary>'
            f'<ul>{"".join(items)}</ul>{more}</details></section>'
        )

    def render_base_page(self, rel: str, theme: str = "light") -> str:
        """Renders a `.base` file's table views, read-only."""
        note = self.vault.read_note(rel)
        title = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if note.error:
            return build_message_page("Cannot open base", note.error, theme)
        graph = self._graph()
        if graph is None:
            return build_message_page(
                title, "The index is still building — reload shortly.", theme
            )
        body = f"<h1>{html.escape(title)}</h1>{render_base(graph, note.text)}"
        return build_page(body, title, theme, typography=self._typo(), extra_css=self._snips())

    def render_text(self, text: str, title: str, theme: str = "light") -> str:
        """Renders standalone markdown text — the in-app documentation pages."""
        env = self._env(f"__document__/{title}")
        body = sanitize(self._render_markdown(split_frontmatter(text).body, env))
        return build_page(body, title, theme, typography=self._typo())

    def render_mindmap(self, rel: str, theme: str = "light") -> str:
        """Renders a note's headings and bullets as a mind-map page."""
        note = self.vault.read_note(rel)
        title = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if note.error:
            return build_message_page("Cannot open note", note.error, theme)
        body = strip_html_comments(strip_block_comments(split_frontmatter(note.text).body))
        back = (
            f'<div class="mindmap-bar"><a class="wikilink" href="{note_uri(rel)}">'
            f"\u25c0 Back to {html.escape(title)}</a> "
            '<span class="dataview-note">(or press Ctrl+M)</span></div>'
        )
        page_body = back + mindmap_body(title, body, rel)
        return build_page(
            page_body, f"{title} (mind map)", theme,
            typography=self._typo(), note_classes="mindmap-note",
        )

    def render_canvas(self, rel: str, theme: str = "light") -> str:
        """Renders a `.canvas` file as a static, positioned page."""
        note = self.vault.read_note(rel)
        title = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if note.error:
            return build_message_page("Cannot open canvas", note.error, theme)

        def note_href(file_rel: str) -> str:
            resolved = resolve_note(self.vault, rel, file_rel)
            return note_uri(resolved.path) if resolved.kind == "note" else ""

        body = canvas_body(parse_canvas(note.text), note_href)
        return build_page(body, title, theme, typography=self._typo(), extra_css=self._snips())

    def render_preview(self, rel: str, theme: str = "light") -> str:
        """Renders the opening slice of a note for the hover preview popover."""
        note = self.vault.read_note(rel)
        title = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if note.error:
            return build_message_page("Cannot preview", note.error, theme)
        body, truncated = _preview_slice(split_frontmatter(note.text).body)
        env = self._env(rel, budget={"left": PREVIEW_EMBED_BUDGET})
        inner = sanitize(self._render_markdown(body, env))
        more = '<div class="preview-more">…</div>' if truncated else ""
        page_body = f'<div class="preview"><h1>{html.escape(title)}</h1>{inner}{more}</div>'
        return build_page(page_body, title, theme, typography=self._typo())

    def _graph(self):
        graph = self.graph_provider() if callable(self.graph_provider) else None
        return graph if graph is not None and graph.ready else None

    def _dataview_html(self, code: str, env: dict) -> str:
        graph = self._graph()
        if graph is None:
            return _inert_dataview(code, "dataview — the index is still building")
        try:
            return DataviewEngine(graph).run_query(code, env.get("source", ""))
        except DqlError as error:
            return _inert_dataview(code, f"dataview — not evaluated: {error}")

    def _inline_dataview_html(self, content: str, env: dict) -> str | None:
        graph = self._graph()
        if graph is None:
            return None
        try:
            markup = DataviewEngine(graph).run_inline(content, env.get("source", ""))
        except DqlError:
            return None
        return f'<span class="dataview-inline">{markup}</span>'

    def _env(
        self,
        rel: str,
        depth: int = 0,
        ancestors: frozenset = frozenset(),
        budget: dict | None = None,
    ) -> dict:
        return {
            "source": rel,
            "depth": depth,
            "ancestors": ancestors | {rel},
            "outline": [],
            "anchor_counts": {},
            "callout_stack": [],
            "embed_budget": budget if budget is not None else {"left": MAX_EMBEDS_PER_PAGE},
        }

    def _render_markdown(self, body: str, env: dict) -> str:
        prepared = strip_block_ids(strip_html_comments(strip_block_comments(body)))
        tokens = self.md.parse(prepared, env)
        self._assign_heading_anchors(tokens, env)
        return self.md.renderer.render(tokens, self.md.options, env)

    def _assign_heading_anchors(self, tokens: list, env: dict) -> None:
        """Gives each heading a stable id and records the outline in order."""
        counts = env["anchor_counts"]
        for index, token in enumerate(tokens):
            if token.type != "heading_open" or env["depth"] > 0:
                continue
            inline = tokens[index + 1] if index + 1 < len(tokens) else None
            text = inline.content if inline is not None else ""
            base = slugify(text)
            counts[base] = counts.get(base, 0) + 1
            anchor = base if counts[base] == 1 else f"{base}-{counts[base]}"
            token.attrSet("id", anchor)
            env["outline"].append(Heading(int(token.tag[1]), text, anchor))

    def _install_render_rules(self) -> None:
        renderer = self
        md = self.md

        def render_wikilink(self_r, tokens, idx, options, env):
            return renderer._wikilink_html(tokens[idx].meta["link"], env)

        def render_embed(self_r, tokens, idx, options, env):
            return renderer._embed_html(tokens[idx].meta["link"], env)

        def render_tag(self_r, tokens, idx, options, env):
            return f'<span class="tag">#{html.escape(tokens[idx].content)}</span>'

        def render_fence(self_r, tokens, idx, options, env):
            return renderer._fence_html(tokens[idx], env)

        def render_blockquote_open(self_r, tokens, idx, options, env):
            meta = tokens[idx].meta or {}
            if "callout" not in meta:
                env["callout_stack"].append("")
                return "<blockquote>\n"
            palette = meta["callout"]
            title = md.renderInline(meta["title"], env)
            icon = '<span class="callout-icon" aria-hidden="true"></span>'
            heading = f'{icon}<span class="callout-title-text">{title}</span>'
            classes = f"callout callout-{palette}"
            if meta["fold"]:
                env["callout_stack"].append("details")
                opened = " open" if meta["fold"] == "+" else ""
                return (
                    f'<details class="{classes}" data-callout="{html.escape(meta["callout_kind"])}"'
                    f'{opened}><summary class="callout-title">{heading}</summary>'
                    f'<div class="callout-body">\n'
                )
            env["callout_stack"].append("div")
            return (
                f'<div class="{classes}" data-callout="{html.escape(meta["callout_kind"])}">'
                f'<div class="callout-title">{heading}</div><div class="callout-body">\n'
            )

        def render_blockquote_close(self_r, tokens, idx, options, env):
            kind = env["callout_stack"].pop() if env["callout_stack"] else ""
            if kind == "details":
                return "</div></details>\n"
            if kind == "div":
                return "</div></div>\n"
            return "</blockquote>\n"

        def render_image(self_r, tokens, idx, options, env):
            return renderer._image_html(tokens, idx, env)

        def render_math_inline(self_r, tokens, idx, options, env):
            return _math_html(tokens[idx].content, display=False)

        def render_math_block(self_r, tokens, idx, options, env):
            return _math_html(tokens[idx].content, display=True)

        def render_code_inline(self_r, tokens, idx, options, env):
            content = tokens[idx].content
            if content.startswith("= ") and len(content) > 2:
                markup = renderer._inline_dataview_html(content[2:], env)
                if markup is not None:
                    return markup
            return f"<code>{html.escape(content)}</code>"

        def render_link_open(self_r, tokens, idx, options, env):
            token = tokens[idx]
            href = token.attrGet("href") or ""
            lowered = href.casefold()
            if lowered.startswith(("http:", "https:")):
                token.attrJoin("class", "external")
            elif lowered.startswith("#"):
                token.attrJoin("class", "internal")
            elif not lowered.startswith(("mailto:", "reader:", "vault:")):
                resolved = resolve_note(renderer.vault, env["source"], unquote(href))
                if resolved.kind == "note":
                    token.attrSet("href", note_uri(resolved.path))
                    token.attrJoin("class", "internal")
                else:
                    token.attrSet("href", "")
                    token.attrJoin("class", "unsupported-link")
            return self_r.renderToken(tokens, idx, options, env)

        md.add_render_rule("code_inline", render_code_inline)
        md.add_render_rule("obsidian_math_inline", render_math_inline)
        md.add_render_rule("obsidian_math_block", render_math_block)
        md.add_render_rule("obsidian_wikilink", render_wikilink)
        md.add_render_rule("obsidian_embed", render_embed)
        md.add_render_rule("obsidian_tag", render_tag)
        md.add_render_rule("fence", render_fence)
        md.add_render_rule("blockquote_open", render_blockquote_open)
        md.add_render_rule("blockquote_close", render_blockquote_close)
        md.add_render_rule("image", render_image)
        md.add_render_rule("link_open", render_link_open)

    def _wikilink_html(self, link: WikiLink, env: dict) -> str:
        label = html.escape(link.label)
        if not link.target and (link.anchor or link.block_id):
            anchor = slugify(link.anchor) if link.anchor else f"block-{link.block_id}"
            return f'<a class="wikilink internal" href="#{anchor}">{label}</a>'
        resolved = resolve_note(self.vault, env["source"], link.target)
        if resolved.kind == "note":
            anchor = slugify(link.anchor.split("#")[-1]) if link.anchor else ""
            href = note_uri(resolved.path, anchor)
            title = html.escape(resolved.path, quote=True)
            return f'<a class="wikilink" href="{href}" title="{title}">{label}</a>'
        if resolved.kind == "ambiguous":
            href = f"reader:///ambiguous/{quote(link.target)}?from={quote(env['source'])}"
            count = len(resolved.candidates)
            return (
                f'<a class="wikilink ambiguous" href="{href}" '
                f'title="{count} notes match — choose one">{label}</a>'
            )
        title = html.escape(f"No note named “{link.target}”", quote=True)
        return f'<span class="wikilink missing" title="{title}">{label}</span>'

    def _embed_html(self, link: WikiLink, env: dict) -> str:
        resolved = resolve_embed(self.vault, env["source"], link.target)
        if resolved.kind == "missing":
            return _embed_error(f"Missing embed: {link.target or link.label}")
        if resolved.kind == "ambiguous":
            count = len(resolved.candidates)
            return _embed_error(f"Ambiguous embed “{link.target}” — {count} matches")
        if resolved.kind == "note":
            return self._note_embed_html(resolved, link, env)
        return _media_embed_html(resolved, link)

    def _note_embed_html(self, resolved: Resolution, link: WikiLink, env: dict) -> str:
        if resolved.path in env["ancestors"]:
            return _embed_error(f"Cyclic embed: {resolved.path}")
        if env["depth"] >= MAX_EMBED_DEPTH:
            return _embed_error(f"Embed depth limit reached at {resolved.path}")
        budget = env["embed_budget"]
        if budget["left"] <= 0:
            return _embed_error(f"Embed limit for this page reached at {resolved.path}")
        budget["left"] -= 1
        note = self.vault.read_note(resolved.path)
        if note.error:
            return _embed_error(note.error)
        body = split_frontmatter(note.text).body
        if link.anchor:
            body = _find_section(body, link.anchor)
            if not body:
                return _embed_error(f"No section “{link.anchor}” in {resolved.path}")
        elif link.block_id:
            body = _find_block(body, link.block_id)
            if not body:
                return _embed_error(f"No block ^{link.block_id} in {resolved.path}")
        inner_env = self._env(resolved.path, env["depth"] + 1, env["ancestors"], budget)
        inner = self._render_markdown(body, inner_env)
        title = html.escape(link.label)
        href = note_uri(resolved.path, slugify(link.anchor) if link.anchor else "")
        return (
            f'<div class="embed embed-note"><div class="embed-title">'
            f'<a class="wikilink" href="{href}">{title}</a></div>'
            f'<div class="embed-body">{inner}</div></div>'
        )

    def _image_html(self, tokens: list, idx: int, env: dict) -> str:
        token = tokens[idx]
        src = token.attrGet("src") or ""
        alt = self.md.renderer.renderInlineAsText(
            token.children or [], self.md.options, env
        )
        width = ""
        if "|" in alt:
            alt, _, tail = alt.rpartition("|")
            if re.fullmatch(r"\d+(x\d+)?", tail.strip()):
                width = tail.strip().split("x")[0]
            else:
                alt = f"{alt}|{tail}"
        lowered = src.casefold()
        if lowered.startswith(("http:", "https:")):
            host = re.sub(r"^https?://([^/]+).*$", r"\1", src)
            return _embed_error(f"Remote image blocked: {html.escape(host)}")
        if lowered.startswith(("data:", "javascript:", "file:")):
            return _embed_error("Blocked image source")
        resolved = resolve_attachment(self.vault, env["source"], unquote(src))
        if resolved.kind != "image":
            return _embed_error(f"Missing image: {html.escape(unquote(src))}")
        size = f' width="{width}"' if width else ""
        return (
            f'<img src="{vault_uri(resolved.path)}" '
            f'alt="{html.escape(alt, quote=True)}"{size} />'
        )

    def _fence_html(self, token, env: dict) -> str:
        info = (token.info or "").strip().split()[0].casefold() if token.info else ""
        code = token.content
        if info == "dataview":
            return self._dataview_html(code, env)
        if info in INERT_FENCES:
            return (
                f'<div class="inert-block"><div class="inert-label">'
                f"{html.escape(info)} — not executed in read-only mode</div>"
                f"<pre><code>{html.escape(code)}</code></pre></div>"
            )
        if info == "mermaid":
            return (
                f'<div class="inert-block"><div class="inert-label">'
                f"mermaid — diagram not rendered</div>"
                f"<pre><code>{html.escape(code)}</code></pre></div>"
            )
        if info:
            try:
                lexer = get_lexer_by_name(info)
            except ClassNotFound:
                lexer = None
            if lexer is not None:
                formatted = highlight(code, lexer, HtmlFormatter(nowrap=True))
                return (
                    f'<pre class="highlight"><code class="language-{html.escape(info)}">'
                    f"{formatted}</code></pre>\n"
                )
        return f"<pre><code>{html.escape(code)}</code></pre>\n"


def note_header(
    rel: str,
    title: str,
    properties: dict,
    body_text: str,
    outline: list,
    mtime: float | None,
) -> str:
    """Context before content: breadcrumb, inline title, and a compact metadata line."""
    crumbs = _crumbs_html(rel)
    heading = "" if _body_opens_with_title(outline, title) else (
        f'<h1 class="inline-title">{html.escape(title)}</h1>'
    )
    meta = _meta_line_html(properties, body_text, mtime)
    if not (crumbs or heading or meta):
        return ""
    return f'<header class="note-header">{crumbs}{heading}{meta}</header>'


def _body_opens_with_title(outline: list, title: str) -> bool:
    """True when the note's first heading is an H1 repeating the filename."""
    first = outline[0] if outline else None
    return (
        first is not None
        and first.level == 1
        and first.text.strip().casefold() == title.strip().casefold()
    )


def _crumbs_html(rel: str) -> str:
    parts = rel.split("/")[:-1]
    if not parts:
        return ""
    links = []
    prefix = ""
    for part in parts:
        prefix = f"{prefix}/{part}" if prefix else part
        href = f"reader:///action/reveal-folder?arg={quote(prefix, safe='')}"
        links.append(f'<a href="{href}">{html.escape(part)}</a>')
    joined = '<span class="crumb-sep">/</span>'.join(links)
    return f'<nav class="crumbs" aria-label="Location">{joined}</nav>'


def _meta_line_html(properties: dict, body_text: str, mtime: float | None) -> str:
    pieces = []
    if mtime is not None:
        stamp = datetime.fromtimestamp(mtime).strftime("%b %-d, %Y")
        pieces.append(f"<span>Updated {html.escape(stamp)}</span>")
    words = len(re.findall(r"\S+", body_text))
    if words:
        pieces.append(f"<span>{words:,} words</span>")
        minutes = round(words / READING_WORDS_PER_MINUTE)
        if minutes >= 2:
            pieces.append(f"<span>~{minutes} min read</span>")
    tags = _header_tags(properties)
    for tag in tags[:MAX_HEADER_TAGS]:
        href = f"reader:///action/tag?arg={quote(tag, safe='')}"
        pieces.append(f'<a class="tag" href="{href}">#{html.escape(tag)}</a>')
    if len(tags) > MAX_HEADER_TAGS:
        pieces.append(f"<span>+{len(tags) - MAX_HEADER_TAGS} more</span>")
    if not pieces:
        return ""
    return f'<div class="note-meta">{"".join(pieces)}</div>'


def _header_tags(properties: dict) -> list[str]:
    values: list[str] = []
    for key in ("tags", "tag"):
        value = properties.get(key) if isinstance(properties, dict) else None
        if isinstance(value, str):
            values.extend(re.split(r"[,\s]+", value))
        elif isinstance(value, list):
            values.extend(str(item) for item in value if item is not None)
    cleaned = [v.strip().lstrip("#") for v in values]
    return list(dict.fromkeys(v for v in cleaned if v))


def page_toc(outline: list) -> str:
    """The wide-window "On this page" rail; CSS hides it below the width it needs."""
    entries = [h for h in outline if h.level <= 3][:MAX_TOC_ENTRIES]
    if len(entries) < 3:
        return ""
    items = "".join(
        f'<li class="toc-l{h.level}"><a href="#{quote(h.anchor)}">{html.escape(h.text)}</a></li>'
        for h in entries
    )
    return (
        '<nav class="page-toc" aria-label="On this page">'
        f'<div class="page-toc-title">On this page</div><ul>{items}</ul></nav>'
    )


def _preview_slice(body: str) -> tuple[str, bool]:
    """Cuts a body to the preview budget at a line boundary, reporting the cut."""
    if len(body) <= PREVIEW_MAX_CHARS:
        return body, False
    kept: list[str] = []
    used = 0
    for line in body.split("\n"):
        if used + len(line) > PREVIEW_MAX_CHARS and kept:
            return "\n".join(kept), True
        kept.append(line)
        used += len(line) + 1
    return "\n".join(kept), True


def _math_html(tex: str, display: bool) -> str:
    """Converts TeX to MathML; anything the converter refuses falls back to source."""
    fallback = f'<code class="math-source">{html.escape(tex)}</code>'
    if len(tex) > MAX_MATH_CHARS:
        return fallback
    try:
        markup = latex_to_mathml(tex, display="block" if display else "inline")
    except Exception:  # noqa: S110 — the converter raises library-specific errors on bad TeX
        return fallback
    if display:
        return f'<div class="math-block">{markup}</div>\n'
    return markup


def _inert_dataview(code: str, label: str) -> str:
    return (
        f'<div class="inert-block"><div class="inert-label">{html.escape(label)}</div>'
        f"<pre><code>{html.escape(code)}</code></pre></div>"
    )


def _embed_error(message: str) -> str:
    return f'<div class="embed embed-error">{html.escape(message)}</div>'


def _media_embed_html(resolved: Resolution, link: WikiLink) -> str:
    """Renders an image, audio, video, or file-card embed for a resolved attachment."""
    uri = vault_uri(resolved.path)
    name = html.escape(resolved.path.rsplit("/", 1)[-1])
    if resolved.kind == "image":
        size = f' width="{link.size.split("x")[0]}"' if link.size else ""
        return f'<img src="{uri}" alt="{name}"{size} />'
    if resolved.kind == "audio":
        return f'<audio controls src="{uri}"></audio>'
    if resolved.kind == "video":
        return f'<video controls src="{uri}"></video>'
    href = f"reader:///external/{quote(resolved.path)}"
    label = "Open" if resolved.kind == "pdf" else "Open with the system default app"
    return (
        f'<div class="embed embed-file"><span class="embed-file-name">{name}</span> '
        f'<a class="external-open" href="{href}">{label}</a></div>'
    )


def _properties_block(properties: dict) -> str:
    """Renders frontmatter as a collapsible Properties panel above the note body."""
    if not properties:
        return ""
    rows = []
    for key, value in properties.items():
        rows.append(
            f'<tr><th scope="row">{html.escape(str(key))}</th>'
            f"<td>{_property_value(value)}</td></tr>"
        )
    return (
        '<details class="properties"><summary>Properties</summary>'
        f'<table class="properties-table">{"".join(rows)}</table></details>'
    )


def _property_value(value) -> str:
    if isinstance(value, list):
        pills = "".join(f'<span class="tag">{html.escape(str(v))}</span> ' for v in value)
        return pills or "—"
    if value is None:
        return "—"
    return html.escape(str(value))


def _message_body(title: str, message: str) -> str:
    return (
        f'<div class="message-state"><h1>{html.escape(title)}</h1>'
        f"<p>{html.escape(message)}</p></div>"
    )


_PAGE_CSS = ""
_PYGMENTS_CSS = ""


def _page_css() -> str:
    """Loads the bundled reader stylesheet plus generated highlight palettes once."""
    global _PAGE_CSS, _PYGMENTS_CSS
    if not _PAGE_CSS:
        _PAGE_CSS = (
            resources.files("obsidian_reader.assets").joinpath("reader.css").read_text("utf-8")
        )
    if not _PYGMENTS_CSS:
        light = HtmlFormatter(style="default").get_style_defs(".theme-light .highlight")
        dark = HtmlFormatter(style="monokai").get_style_defs(".theme-dark .highlight")
        _PYGMENTS_CSS = f"{light}\n{dark}"
    return f"{_PAGE_CSS}\n{_PYGMENTS_CSS}"


# Reading-comfort presets; unknown values fall back to the stylesheet's own defaults.
_FONT_STACKS = {
    "serif": "'Noto Serif', 'Liberation Serif', Georgia, serif",
    "sans": "'Cantarell', 'Ubuntu', 'Segoe UI', system-ui, sans-serif",
    "mono": "'Ubuntu Mono', 'Source Code Pro', 'DejaVu Sans Mono', monospace",
}
_LINE_WIDTHS = {"narrow": "35rem", "wide": "58rem", "full": "none"}
_LINE_HEIGHTS = {"compact": "1.45", "relaxed": "1.85"}


def _typography_css(typography: dict | None) -> str:
    """Builds the override style block for the reader's typography preferences."""
    if not typography:
        return ""
    rules = []
    font = _FONT_STACKS.get(typography.get("font", ""))
    if font:
        rules.append(f"body {{ font-family: {font}; }}")
    width = _LINE_WIDTHS.get(typography.get("width", ""))
    if width:
        rules.append(f"main.note {{ max-width: {width}; }}")
    height = _LINE_HEIGHTS.get(typography.get("spacing", ""))
    if height:
        rules.append(f"body {{ line-height: {height}; }}")
    return f"<style>{' '.join(rules)}</style>" if rules else ""


def _css_classes(properties: dict) -> str:
    """Obsidian applies `cssclasses` frontmatter to the preview container; so do we."""
    values = []
    for key in ("cssclasses", "cssclass"):
        value = properties.get(key) if isinstance(properties, dict) else None
        if isinstance(value, str):
            values.extend(value.split())
        elif isinstance(value, list):
            values.extend(str(item) for item in value)
    safe = [v for v in values if re.fullmatch(r"[A-Za-z0-9_-]+", v)]
    return " ".join(dict.fromkeys(safe))


def build_page(
    body: str,
    title: str,
    theme: str = "light",
    lossy: bool = False,
    typography: dict | None = None,
    extra_css: str = "",
    note_classes: str = "",
) -> str:
    """Wraps sanitized body markup in the full page shell with CSP and theme CSS."""
    notice = (
        '<div class="decode-notice">This file is not valid UTF-8; '
        "undecodable bytes are shown as replacement characters.</div>"
        if lossy
        else ""
    )
    theme_class = "theme-dark" if theme == "dark" else "theme-light"
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
        "img-src vault:; media-src vault:; style-src 'unsafe-inline';\">"
        f"<title>{html.escape(title)}</title><style>{_page_css()}</style>"
        f"{_typography_css(typography)}{_snippet_style(extra_css)}</head>"
        f"<body class='{theme_class}' dir='auto'>{notice}"
        f"<main class='note markdown-preview-view {html.escape(note_classes, quote=True)}'>"
        f"{body}</main></body></html>"
    )


def _snippet_style(extra_css: str) -> str:
    if not extra_css:
        return ""
    return f"<style>{extra_css}</style>"


def build_source_page(source: str, title: str, theme: str = "light") -> str:
    """Builds the raw-source fallback view for the current note."""
    body = f'<pre class="raw-source">{html.escape(source)}</pre>'
    return build_page(body, f"{title} (source)", theme)


def build_message_page(title: str, message: str, theme: str = "light") -> str:
    """Builds an in-pane state page for errors, placeholders, and empty states."""
    return build_page(_message_body(title, message), title, theme)
