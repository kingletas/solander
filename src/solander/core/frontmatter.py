"""Splits a note into YAML frontmatter and body, without trusting either."""

import os
from dataclasses import dataclass, field

import yaml

# Anchors expand at render time, so a few hundred bytes of aliases can become
# gigabytes of output; properties never legitimately need them, so they are refused.
MAX_FRONTMATTER_BYTES = int(os.environ.get("READER_MAX_FRONTMATTER_BYTES", str(128 * 1024)))


# LibYAML parses several times faster than the pure-Python scanner, and every
# note carrying frontmatter pays that cost on every index build. It is absent
# only from a PyYAML built without the C extension, where the slower loader is
# still correct.
_SafeLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class _FrontmatterLoader(_SafeLoader):
    """Safe loader carrying Obsidian's reading of bare yes/no/on/off."""


# YAML 1.1 reads bare yes/no/on/off as booleans; Obsidian does not, and a vault
# writing `Outage: Yes` means the string. Only true/false stay booleans here.
_FrontmatterLoader.yaml_implicit_resolvers = {
    key: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag != "tag:yaml.org,2002:bool" or key in ("t", "T", "f", "F")
    ]
    for key, resolvers in _SafeLoader.yaml_implicit_resolvers.items()
}


def _refuse_aliases(raw: str) -> None:
    """Raises before any alias is expanded, over the parser's own event stream.

    This is a pass rather than a `compose_node` override because LibYAML composes
    in C and never calls one — a subclass that overrides it loads aliases anyway,
    with nothing to say the refusal has stopped happening.
    """
    for event in yaml.parse(raw, Loader=_SafeLoader):
        if isinstance(event, yaml.AliasEvent):
            raise yaml.YAMLError("aliases are not allowed in frontmatter")


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
    if not text.startswith(("---\n", "---\r\n")) and text.strip() != "---":
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
        _refuse_aliases(raw)
        parsed = yaml.load(raw, Loader=_FrontmatterLoader)  # noqa: S506 — SafeLoader subclass
    except yaml.YAMLError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
