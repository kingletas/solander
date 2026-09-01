"""Filename and content search over the fixture vault."""

from obsidian_reader.core.graph import VaultGraph
from obsidian_reader.core.search import SearchIndex, parse_query, search_filenames


def test_filename_search_ranks_name_matches_first(vault):
    hits = search_filenames(vault, "alpha")
    assert hits[0].path == "Projects/Alpha.md"


def test_filename_search_matches_all_words(vault):
    hits = search_filenames(vault, "meeting personal")
    assert [h.path for h in hits] == ["Personal/Meeting Notes.md"]


def test_content_search_returns_snippets(vault):
    index = SearchIndex.build(vault)
    hits = index.search_content("ships soon")
    assert [h.path for h in hits] == ["Projects/Alpha.md"]
    assert "ships soon" in hits[0].snippet


def test_content_search_is_case_insensitive(vault):
    index = SearchIndex.build(vault)
    assert index.search_content("SHIPS") != []


def test_empty_query_returns_nothing(vault):
    index = SearchIndex.build(vault)
    assert index.search_content("   ") == []
    assert search_filenames(vault, "") == []


def test_progress_callback_reports_completion(vault):
    seen = []
    SearchIndex.build(vault, progress=lambda done, total: seen.append((done, total)))
    assert seen[-1][0] == seen[-1][1] == len(vault.notes)


def test_parse_query_splits_operators_from_words(vault):
    parsed = parse_query("timeline path:Projects file:alpha tag:#Home odd:thing")
    assert parsed.words == ("timeline", "odd:thing")
    assert parsed.paths == ("projects",)
    assert parsed.files == ("alpha",)
    assert parsed.tags == ("home",)


def test_path_operator_narrows_content_hits(vault):
    index = SearchIndex.build(vault)
    hits = index.search_content("meeting path:personal")
    assert [h.path for h in hits] == ["Personal/Meeting Notes.md"]


def test_file_operator_matches_the_filename_only(vault):
    index = SearchIndex.build(vault)
    assert [h.path for h in index.search_content("file:alpha")] == ["Projects/Alpha.md"]


def test_tag_operator_uses_the_graph_tags(vault):
    index = SearchIndex.build(vault)
    graph = VaultGraph.build(vault)
    assert [h.path for h in index.search_content("tag:home", graph.note_tags)] == ["Index.md"]


def test_tag_operator_matches_nested_children(vault):
    index = SearchIndex.build(vault)
    graph = VaultGraph.build(vault)
    assert [h.path for h in index.search_content("tag:project", graph.note_tags)] == ["Index.md"]


def test_tag_operator_without_tags_matches_nothing(vault):
    index = SearchIndex.build(vault)
    assert index.search_content("tag:home", None) == []


def test_filter_only_query_returns_hits_without_snippets(vault):
    index = SearchIndex.build(vault)
    hits = index.search_content("path:projects")
    assert hits and all(h.snippet == "" for h in hits)
    assert all(h.path.startswith("Projects/") for h in hits)
