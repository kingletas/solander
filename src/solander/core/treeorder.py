"""The order the file tree lists a folder in: by name, newest first, or by type."""

from dataclasses import dataclass
from pathlib import PurePosixPath

TREE_SORTS = ("name", "modified", "type")


@dataclass(frozen=True)
class Entry:
    """One thing in a folder, with only what ordering it needs."""

    name: str
    is_dir: bool
    mtime: float = 0.0


def tree_sort(value: str) -> str:
    """A saved sort, or name order when the value is not one this tree knows."""
    return value if value in TREE_SORTS else "name"


def tree_order(entries, sort: str = "name") -> list:
    """Folders first by name, then files in the chosen order, name breaking every tie."""

    def name(entry) -> str:
        return entry.name.casefold()

    folders = sorted((entry for entry in entries if entry.is_dir), key=name)
    files = [entry for entry in entries if not entry.is_dir]
    sort = tree_sort(sort)
    if sort == "modified":
        files.sort(key=lambda entry: (-entry.mtime, name(entry)))
    elif sort == "type":
        files.sort(key=lambda entry: (PurePosixPath(name(entry)).suffix, name(entry)))
    else:
        files.sort(key=name)
    return folders + files
