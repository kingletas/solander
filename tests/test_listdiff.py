"""The list edits a refresh applies: they reach the new list and leave shared items alone."""

from solander.core.listdiff import splices


def apply(old, new):
    """Applies the edits to a list of (key, identity) pairs, as a list store would."""
    rows = [(key, f"old:{key}") for key in old]
    for position, removed, start, end in splices(old, new):
        rows[position : position + removed] = [(key, f"new:{key}") for key in new[start:end]]
    return rows


def test_no_change_makes_no_edits():
    assert splices(["a", "b", "c"], ["a", "b", "c"]) == []


def test_the_edits_reach_the_new_list():
    old = ["Archive", "Projects", "a.md", "c.md"]
    new = ["Journal", "Projects", "b.md", "c.md", "d.md"]
    assert [key for key, _ in apply(old, new)] == new


def test_a_new_file_leaves_every_other_row_as_it_was():
    old = ["Archive", "Projects", "a.md", "c.md"]
    rows = apply(old, ["Archive", "Projects", "a.md", "b.md", "c.md"])
    assert rows == [
        ("Archive", "old:Archive"),
        ("Projects", "old:Projects"),
        ("a.md", "old:a.md"),
        ("b.md", "new:b.md"),
        ("c.md", "old:c.md"),
    ]


def test_a_deleted_folder_takes_only_itself():
    rows = apply(["Archive", "Projects", "a.md"], ["Projects", "a.md"])
    assert rows == [("Projects", "old:Projects"), ("a.md", "old:a.md")]


def test_everything_replaced_still_arrives():
    assert [key for key, _ in apply(["a", "b"], ["x", "y", "z"])] == ["x", "y", "z"]


def test_from_and_to_empty():
    assert [key for key, _ in apply([], ["a", "b"])] == ["a", "b"]
    assert apply(["a", "b"], []) == []
