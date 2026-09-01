"""Splits a note into YAML frontmatter and body, without trusting either."""

from dataclasses import dataclass, field

import yaml


@dataclass(frozen=True)
class SplitNote:
    """A note's parsed frontmatter mapping and the Markdown body below it."""

    properties: dict = field(default_factory=dict)
    body: str = ""
    raw_frontmatter: str = ""


def split_frontmatter(text: str) -> SplitNote:
    """Separates a leading `---` YAML block from the body, tolerating malformed YAML."""
    if not text.startswith("---\n") and text.strip() != "---":
        return SplitNote(body=text)
    lines = text.split("\n")
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            raw = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            try:
                parsed = yaml.safe_load(raw)
            except yaml.YAMLError:
                parsed = None
            if not isinstance(parsed, dict):
                parsed = {}
            return SplitNote(properties=parsed, body=body, raw_frontmatter=raw)
    return SplitNote(body=text)
