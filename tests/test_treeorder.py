"""The order the file tree lists a folder in."""

from solander.core.treeorder import TREE_SORTS, Entry, tree_order, tree_sort


def names(entries):
    return [entry.name for entry in entries]


FOLDER = [
    Entry("zeta.md", False, 300.0),
    Entry("Archive", True, 900.0),
    Entry("alpha.md", False, 100.0),
    Entry("board.canvas", False, 200.0),
    Entry("Beta.md", False, 300.0),
    Entry("assets", True, 50.0),
    Entry("chart.base", False, 400.0),
]


def test_by_name_folders_come_first_and_case_is_ignored():
    assert names(tree_order(FOLDER, "name")) == [
        "Archive", "assets", "alpha.md", "Beta.md", "board.canvas", "chart.base", "zeta.md",
    ]


def test_by_modified_the_newest_file_leads_and_name_breaks_a_tie():
    assert names(tree_order(FOLDER, "modified")) == [
        "Archive", "assets", "chart.base", "Beta.md", "zeta.md", "board.canvas", "alpha.md",
    ]


def test_by_type_files_group_by_extension_then_name():
    assert names(tree_order(FOLDER, "type")) == [
        "Archive", "assets", "chart.base", "board.canvas", "alpha.md", "Beta.md", "zeta.md",
    ]


def test_folders_keep_name_order_whatever_the_sort():
    for sort in TREE_SORTS:
        assert names(tree_order(FOLDER, sort))[:2] == ["Archive", "assets"]


def test_an_unknown_sort_is_name_order():
    assert tree_sort("size") == "name"
    assert tree_sort("") == "name"
    assert tree_sort("modified") == "modified"
    assert names(tree_order(FOLDER, "size")) == names(tree_order(FOLDER, "name"))
