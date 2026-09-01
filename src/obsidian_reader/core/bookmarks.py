"""Reads the vault's Obsidian bookmarks out of `.obsidian/bookmarks.json`, read-only."""

import json
import os
from dataclasses import dataclass

from .vault import Vault

# The store is vault content and therefore untrusted: both bounds keep a hostile
# file from turning the bookmarks panel into a memory or recursion problem.
MAX_BOOKMARK_BYTES = int(os.environ.get("READER_MAX_BOOKMARK_BYTES", str(1024 * 1024)))
MAX_BOOKMARKS = int(os.environ.get("READER_MAX_BOOKMARKS", "500"))

MAX_GROUP_DEPTH = 12


@dataclass(frozen=True)
class Bookmark:
    """One bookmarked note: its vault path, display title, and group path."""

    rel: str
    title: str
    group: str = ""


def read_bookmarks(vault: Vault) -> list[Bookmark]:
    """Returns the vault's file bookmarks in order, groups flattened, missing files dropped."""
    path = vault.root / ".obsidian" / "bookmarks.json"
    try:
        raw = path.read_bytes()
    except OSError:
        return []
    if len(raw) > MAX_BOOKMARK_BYTES:
        return []
    try:
        parsed = json.loads(raw)
    except ValueError:
        return []
    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        return []
    bookmarks: list[Bookmark] = []
    stack = [(item, "", 0) for item in reversed(items)]
    while stack and len(bookmarks) < MAX_BOOKMARKS:
        item, group, depth = stack.pop()
        if not isinstance(item, dict) or depth > MAX_GROUP_DEPTH:
            continue
        kind = item.get("type")
        if kind == "group" and isinstance(item.get("items"), list):
            title = item.get("title")
            name = title if isinstance(title, str) and title.strip() else ""
            child_group = f"{group} / {name}".strip(" /") if name else group
            stack.extend((child, child_group, depth + 1) for child in reversed(item["items"]))
        elif kind == "file" and isinstance(item.get("path"), str):
            rel = item["path"]
            if not vault.has_file(rel):
                continue
            title = item.get("title")
            display = title if isinstance(title, str) and title.strip() else ""
            fallback = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            bookmarks.append(Bookmark(rel=rel, title=display or fallback, group=group))
    return bookmarks
