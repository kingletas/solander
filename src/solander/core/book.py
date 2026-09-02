"""Orders a folder of notes into a readable book: chapters, titles, neighbors."""

import re

_NUMBER = re.compile(r"(\d+)")
_LEADING_ORDER = re.compile(r"^\d+\s*[-—.·]?\s*")


def natural_key(name: str):
    """Sorts "2" before "10" the way a shelf would."""
    return [int(part) if part.isdigit() else part.casefold()
            for part in _NUMBER.split(name)]


def chapters_in(vault, folder: str) -> list[str]:
    """The notes sitting directly in a folder, in reading order."""
    prefix = folder.rstrip("/") + "/"
    found = [
        rel for rel in vault.notes
        if rel.startswith(prefix) and "/" not in rel[len(prefix):]
    ]
    return sorted(found, key=lambda rel: natural_key(rel.rsplit("/", 1)[-1]))


def chapter_title(rel: str) -> str:
    """A chapter's display name: the stem with its ordering prefix removed."""
    stem = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    cleaned = _LEADING_ORDER.sub("", stem).strip()
    return cleaned or stem
