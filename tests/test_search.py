"""Filename and content search over the fixture vault."""

from obsidian_reader.core.search import SearchIndex, search_filenames


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
