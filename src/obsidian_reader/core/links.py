"""Parses Obsidian wikilink syntax into a structured link."""

import re
import unicodedata
from dataclasses import dataclass

# Obsidian escapes the alias pipe as `\|` inside tables; both spellings separate the alias.
_ESCAPED_PIPE = re.compile(r"\\\|")


@dataclass(frozen=True)
class WikiLink:
    """One parsed `[[...]]` reference: where it points and what it displays."""

    target: str
    anchor: str = ""
    block_id: str = ""
    alias: str = ""
    size: str = ""

    @property
    def label(self) -> str:
        """The text shown for the link, falling back through alias, target, and anchor."""
        if self.alias:
            return self.alias
        if self.target and self.anchor:
            return f"{self.target} > {self.anchor}"
        if self.target:
            return self.target
        if self.anchor:
            return self.anchor
        return f"^{self.block_id}" if self.block_id else ""


def parse_wikilink(inner: str) -> WikiLink:
    """Splits the inside of a `[[...]]` into target, anchor or block id, and alias."""
    inner = _ESCAPED_PIPE.sub("|", inner)
    body, _, alias = inner.partition("|")
    body = body.strip()
    alias = alias.strip()
    target, _, fragment = body.partition("#")
    target = target.strip()
    fragment = fragment.strip()
    if fragment.startswith("^"):
        return WikiLink(target=target, block_id=fragment[1:], alias=alias)
    return WikiLink(target=target, anchor=fragment, alias=alias)


def parse_embed(inner: str) -> WikiLink:
    """Splits the inside of a `![[...]]`, treating a numeric alias as an image size."""
    link = parse_wikilink(inner)
    if link.alias and re.fullmatch(r"\d+(x\d+)?", link.alias):
        return WikiLink(
            target=link.target, anchor=link.anchor, block_id=link.block_id, size=link.alias
        )
    return link


def slugify(heading: str) -> str:
    """Normalizes a heading into the anchor id used for `#Heading` navigation."""
    text = unicodedata.normalize("NFC", heading).casefold().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-") or "section"


def normalize_name(name: str) -> str:
    """Normalizes a note name for case- and accent-stable index lookups."""
    stem = name[:-3] if name.casefold().endswith(".md") else name
    return unicodedata.normalize("NFC", stem).casefold()
