"""Marks every search word in a rendered page, so a note opened from search shows why it matched.

The reader runs no scripts, and WebKit's own find can light one string at a time, so the
words are marked in the HTML before the page is shown. Matching follows the index: case and
accents are ignored, and a word matches at the start of any word it begins.
"""

import re
import unicodedata

FIRST_HIT_ID = "search-hit"

# Elements whose text is not reading text: never marked.
_SKIPPED = {"head", "title", "style", "script", "svg", "math", "textarea", "template"}
_TAG = re.compile(r"<!--.*?-->|<[^>]*>", re.S)
_TAG_NAME = re.compile(r"<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9-]*)")
_ENTITY = re.compile(r"&[#a-zA-Z0-9]+;")


def mark_terms(page: str, terms) -> tuple[str, int]:
    """Returns the page with each term marked, and how many marks it made."""
    folded_terms = [term for term in (_fold(t) for t in terms) if term]
    if not folded_terms:
        return page, 0
    out: list[str] = []
    depth = 0
    count = 0
    position = 0
    for tag in _TAG.finditer(page):
        text = page[position : tag.start()]
        if text:
            marked, made = (text, 0) if depth else _mark_text(text, folded_terms, count)
            out.append(marked)
            count += made
        out.append(tag.group(0))
        depth = _depth_after(tag.group(0), depth)
        position = tag.end()
    tail = page[position:]
    if tail:
        marked, made = (tail, 0) if depth else _mark_text(tail, folded_terms, count)
        out.append(marked)
        count += made
    return "".join(out), count


def _depth_after(tag: str, depth: int) -> int:
    """How deep inside skipped elements the text after this tag sits."""
    match = _TAG_NAME.match(tag)
    if match is None or match.group(2).lower() not in _SKIPPED or tag.endswith("/>"):
        return depth
    return max(depth - 1, 0) if match.group(1) else depth + 1


def _mark_text(text: str, terms: list[str], already: int) -> tuple[str, int]:
    """Marks the terms in one run of text, keeping entities whole."""
    folded, origin = _fold_with_origin(text)
    spans: list[tuple[int, int]] = []
    for term in terms:
        start = folded.find(term)
        while start >= 0:
            end = start + len(term)
            if start == 0 or not folded[start - 1].isalnum():
                spans.append((origin[start], origin[end - 1] + 1))
            start = folded.find(term, start + 1)
    entities = [match.span() for match in _ENTITY.finditer(text)]
    kept: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if kept and start < kept[-1][1]:
            continue
        if any(start < e_end and end > e_start for e_start, e_end in entities):
            continue
        kept.append((start, end))
    if not kept:
        return text, 0
    out: list[str] = []
    cursor = 0
    for index, (start, end) in enumerate(kept):
        first = already == 0 and index == 0
        anchor = f' id="{FIRST_HIT_ID}"' if first else ""
        opening = f'<mark class="search-hit"{anchor}>'
        out.append(text[cursor:start] + opening + text[start:end] + "</mark>")
        cursor = end
    out.append(text[cursor:])
    return "".join(out), len(kept)


def _fold_with_origin(text: str) -> tuple[str, list[int]]:
    """The folded text, and for each of its characters the index it came from."""
    folded: list[str] = []
    origin: list[int] = []
    for index, char in enumerate(text):
        for piece in _fold(char):
            folded.append(piece)
            origin.append(index)
    return "".join(folded), origin


def _fold(text: str) -> str:
    """Case and accents removed, as the index removes them."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()
