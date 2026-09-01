"""Configures markdown-it with the Obsidian inline syntax: wikilinks, embeds, highlights, tags."""

import re

from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

from .links import parse_embed, parse_wikilink

# Extended task states beyond GFM's `x` and space, rendered as styled markers.
TASK_STATES = {
    "-": "cancelled",
    "/": "in-progress",
    ">": "forwarded",
    "<": "scheduled",
    "?": "question",
    "!": "important",
    "*": "star",
}

_TAG_BODY = re.compile(r"[\w/-]+")
_TAG_BOUNDARY = " \t\n([{'\"“‘>,;:"
_FENCE_LINE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def strip_block_comments(text: str) -> str:
    """Removes `%%` comment spans that cross lines, leaving fenced code untouched."""
    lines = text.split("\n")
    output: list[str] = []
    fence = ""
    in_comment = False
    for line in lines:
        match = _FENCE_LINE.match(line)
        if not in_comment and match:
            marker = match.group(1)
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
            output.append(line)
            continue
        if fence:
            output.append(line)
            continue
        result = []
        position = 0
        while position < len(line):
            index = line.find("%%", position)
            if index < 0:
                if not in_comment:
                    result.append(line[position:])
                break
            if not in_comment:
                result.append(line[position:index])
            in_comment = not in_comment
            position = index + 2
        output.append("".join(result))
    return "\n".join(output)


def strip_html_comments(text: str) -> str:
    """Removes `<!-- -->` comments outside fenced code, as Obsidian's reading view does."""
    lines = text.split("\n")
    output: list[str] = []
    fence = ""
    in_comment = False
    for line in lines:
        match = _FENCE_LINE.match(line)
        if not in_comment and match:
            marker = match.group(1)
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
            output.append(line)
            continue
        if fence:
            output.append(line)
            continue
        result = []
        position = 0
        while position < len(line):
            if in_comment:
                index = line.find("-->", position)
                if index < 0:
                    break
                in_comment = False
                position = index + 3
            else:
                index = line.find("<!--", position)
                if index < 0:
                    result.append(line[position:])
                    break
                result.append(line[position:index])
                in_comment = True
                position = index + 4
        output.append("".join(result))
    return "\n".join(output)


def _wikilink_rule(state, silent: bool) -> bool:
    """Parses `[[...]]` and `![[...]]` into wikilink and embed tokens."""
    src = state.src
    position = state.pos
    embed = False
    if src.startswith("![[", position):
        embed = True
        position += 1
    elif not src.startswith("[[", position):
        return False
    end = src.find("]]", position + 2)
    if end < 0:
        return False
    inner = src[position + 2 : end]
    if "\n" in inner or not inner.strip():
        return False
    if not silent:
        if embed:
            token = state.push("obsidian_embed", "", 0)
            token.meta = {"link": parse_embed(inner)}
        else:
            token = state.push("obsidian_wikilink", "", 0)
            token.meta = {"link": parse_wikilink(inner)}
        token.content = inner
    state.pos = end + 2
    return True


def _highlight_rule(state, silent: bool) -> bool:
    """Parses `==text==` into a mark span with its inner Markdown intact."""
    src = state.src
    position = state.pos
    if not src.startswith("==", position):
        return False
    end = src.find("==", position + 2)
    if end < 0:
        return False
    inner = src[position + 2 : end]
    if not inner.strip() or "\n" in inner:
        return False
    if not silent:
        state.push("mark_open", "mark", 1)
        children: list = []
        state.md.inline.parse(inner, state.md, state.env, children)
        state.tokens.extend(children)
        state.push("mark_close", "mark", -1)
    state.pos = end + 2
    return True


def _comment_rule(state, silent: bool) -> bool:
    """Drops a same-line `%%comment%%` span from the output."""
    src = state.src
    position = state.pos
    if not src.startswith("%%", position):
        return False
    end = src.find("%%", position + 2)
    if end < 0 or "\n" in src[position + 2 : end]:
        return False
    state.pos = end + 2
    return True


def _tag_rule(state, silent: bool) -> bool:
    """Parses an inline `#tag` at a word boundary into a styled, non-navigating pill."""
    src = state.src
    position = state.pos
    if src[position] != "#":
        return False
    if position > 0 and src[position - 1] not in _TAG_BOUNDARY:
        return False
    match = _TAG_BODY.match(src, position + 1)
    if not match:
        return False
    body = match.group(0)
    if body.replace("/", "").replace("-", "").replace("_", "").isdigit():
        return False
    if not silent:
        token = state.push("obsidian_tag", "", 0)
        token.content = body
    state.pos = match.end()
    return True


def _extended_tasks_rule(state) -> None:
    """Restyles list items whose first text is an extended task marker like `[-]`."""
    tokens = state.tokens
    for index in range(len(tokens) - 2):
        if (
            tokens[index].type == "list_item_open"
            and tokens[index + 1].type == "paragraph_open"
            and tokens[index + 2].type == "inline"
        ):
            inline = tokens[index + 2]
            content = inline.content
            if len(content) >= 4 and content[0] == "[" and content[2] == "]" and content[3] == " ":
                name = TASK_STATES.get(content[1])
                if name:
                    inline.content = content[4:]
                    tokens[index].attrJoin("class", f"task-list-item task-{name}")


def build_parser() -> MarkdownIt:
    """Builds the configured parser: CommonMark + GFM + the Obsidian layer, raw HTML off."""
    md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": False})
    md.enable(["table", "strikethrough", "linkify"])
    md.use(footnote_plugin)
    md.use(tasklists_plugin, enabled=False)
    md.inline.ruler.before("link", "obsidian_wikilink", _wikilink_rule)
    md.inline.ruler.before("obsidian_wikilink", "obsidian_comment", _comment_rule)
    md.inline.ruler.before("emphasis", "obsidian_highlight", _highlight_rule)
    md.inline.ruler.push("obsidian_tag", _tag_rule)
    md.core.ruler.before("inline", "obsidian_tasks", _extended_tasks_rule)
    return md
