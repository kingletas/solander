"""Turns Obsidian callout blockquotes into styled, optionally foldable blocks."""

import re

# Every documented Obsidian type, mapped to the palette class that styles it.
CALLOUT_TYPES = {
    "note": "note",
    "abstract": "abstract",
    "summary": "abstract",
    "tldr": "abstract",
    "info": "info",
    "todo": "info",
    "tip": "tip",
    "hint": "tip",
    "important": "tip",
    "success": "success",
    "check": "success",
    "done": "success",
    "question": "question",
    "help": "question",
    "faq": "question",
    "warning": "warning",
    "caution": "warning",
    "attention": "warning",
    "failure": "failure",
    "fail": "failure",
    "missing": "failure",
    "danger": "danger",
    "error": "danger",
    "bug": "bug",
    "example": "example",
    "quote": "quote",
    "cite": "quote",
}

_CALLOUT_HEAD = re.compile(r"^\[!([\w-]+)\]([+-]?)[ \t]*([^\n]*)")


def callouts_rule(state) -> None:
    """Marks blockquotes that open with `[!type]` so the renderer emits callouts."""
    tokens = state.tokens
    for index in range(len(tokens) - 2):
        if not (
            tokens[index].type == "blockquote_open"
            and tokens[index + 1].type == "paragraph_open"
            and tokens[index + 2].type == "inline"
        ):
            continue
        inline = tokens[index + 2]
        match = _CALLOUT_HEAD.match(inline.content)
        if not match:
            continue
        kind = match.group(1).casefold()
        palette = CALLOUT_TYPES.get(kind, "note")
        fold = match.group(2)
        title = match.group(3).strip() or kind.capitalize()
        tokens[index].meta = {
            "callout": palette,
            "callout_kind": kind,
            "fold": fold,
            "title": title,
        }
        remainder = inline.content[match.end() :].lstrip("\n")
        inline.content = remainder
        if not remainder:
            tokens[index + 1].hidden = True
            index_close = index + 3
            if index_close < len(tokens) and tokens[index_close].type == "paragraph_close":
                tokens[index_close].hidden = True
