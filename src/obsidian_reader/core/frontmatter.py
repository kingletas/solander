"""Splits a note into YAML frontmatter and body, without trusting either."""

import os
from dataclasses import dataclass, field

import yaml

# Anchors expand at render time, so a few hundred bytes of aliases can become
# gigabytes of output; properties never legitimately need them, so they are refused.
MAX_FRONTMATTER_BYTES = int(os.environ.get("READER_MAX_FRONTMATTER_BYTES", str(128 * 1024)))


class _NoAliasLoader(yaml.SafeLoader):
    """SafeLoader that refuses alias expansion outright."""

    def compose_node(self, parent, index):
        event = self.peek_event()
        if isinstance(event, yaml.AliasEvent):
            raise yaml.YAMLError("aliases are not allowed in frontmatter")
        return super().compose_node(parent, index)


@dataclass(frozen=True)
class SplitNote:
    """A note's parsed frontmatter mapping and the Markdown body below it."""

    properties: dict = field(default_factory=dict)
    body: str = ""
    raw_frontmatter: str = ""


def split_frontmatter(text: str, parse_properties: bool = True) -> SplitNote:
    """Separates a leading `---` YAML block from the body, tolerating malformed YAML.

    `parse_properties=False` skips the YAML parse and returns empty properties —
    the raw block is still split off, which is all a bulk pass over a vault needs.
    """
    if not text.startswith("---\n") and text.strip() != "---":
        return SplitNote(body=text)
    lines = text.split("\n")
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            raw = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            properties = _parse_properties(raw) if parse_properties else {}
            return SplitNote(properties=properties, body=body, raw_frontmatter=raw)
    return SplitNote(body=text)


def _parse_properties(raw: str) -> dict:
    """Parses the YAML block defensively; anything hostile degrades to no properties."""
    if len(raw.encode("utf-8", errors="replace")) > MAX_FRONTMATTER_BYTES:
        return {}
    try:
        parsed = yaml.load(raw, Loader=_NoAliasLoader)  # noqa: S506 — SafeLoader subclass
    except yaml.YAMLError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
