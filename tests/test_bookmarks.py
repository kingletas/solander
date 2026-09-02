"""The bookmarks reader: flattening, hostile input, and the read-only bounds."""

import json

from solander.core.bookmarks import read_bookmarks


def _write(vault_dir, payload) -> None:
    (vault_dir / ".obsidian" / "bookmarks.json").write_text(json.dumps(payload))


def test_file_bookmarks_flatten_with_group_paths(vault, vault_dir):
    _write(
        vault_dir,
        {
            "items": [
                {"type": "file", "path": "Index.md", "title": "Home"},
                {
                    "type": "group",
                    "title": "Work",
                    "items": [{"type": "file", "path": "Projects/Alpha.md"}],
                },
            ]
        },
    )
    bookmarks = read_bookmarks(vault)
    assert [(b.rel, b.title, b.group) for b in bookmarks] == [
        ("Index.md", "Home", ""),
        ("Projects/Alpha.md", "Alpha", "Work"),
    ]


def test_missing_files_and_other_types_are_dropped(vault, vault_dir):
    _write(
        vault_dir,
        {
            "items": [
                {"type": "file", "path": "Gone.md"},
                {"type": "search", "query": "tag:x"},
                {"type": "file", "path": "../outside.md"},
                {"type": "file", "path": "Index.md"},
            ]
        },
    )
    assert [b.rel for b in read_bookmarks(vault)] == ["Index.md"]


def test_no_bookmarks_file_means_no_bookmarks(vault):
    assert read_bookmarks(vault) == []


def test_malformed_json_degrades_to_empty(vault, vault_dir):
    (vault_dir / ".obsidian" / "bookmarks.json").write_text("{not json")
    assert read_bookmarks(vault) == []


def test_deep_nesting_is_bounded(vault, vault_dir):
    inner: dict = {"type": "file", "path": "Index.md"}
    for _ in range(50):
        inner = {"type": "group", "title": "g", "items": [inner]}
    _write(vault_dir, {"items": [inner]})
    assert read_bookmarks(vault) == []


def test_bookmark_count_is_capped(vault, vault_dir, monkeypatch):
    import solander.core.bookmarks as bookmarks_module

    monkeypatch.setattr(bookmarks_module, "MAX_BOOKMARKS", 3)
    _write(vault_dir, {"items": [{"type": "file", "path": "Index.md"}] * 10})
    assert len(read_bookmarks(vault)) == 3
