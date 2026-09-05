"""Filename and content search over the fixture vault, through the persistent index."""

from solander.core.indexing import sync_indexes
from solander.core.search import (
    SearchHit,
    VaultSearch,
    demote,
    parse_query,
    search_filenames,
)
from solander.core.store import IndexStore


def make_search(vault, tmp_path):
    store = IndexStore(tmp_path / "index.db")
    result = sync_indexes(vault, store)
    search = VaultSearch(store)
    search.ready = True
    return search, result.graph


def test_filename_search_ranks_name_matches_first(vault):
    hits = search_filenames(vault, "alpha")
    assert hits[0].path == "Projects/Alpha.md"


def test_filename_search_matches_all_words(vault):
    hits = search_filenames(vault, "meeting personal")
    assert [h.path for h in hits] == ["Personal/Meeting Notes.md"]


def test_content_search_returns_snippets(vault, tmp_path):
    search, _ = make_search(vault, tmp_path)
    hits = search.search_content("ships soon")
    assert [h.path for h in hits] == ["Projects/Alpha.md"]
    assert "ships soon" in hits[0].snippet.casefold()


def test_content_search_is_case_insensitive(vault, tmp_path):
    search, _ = make_search(vault, tmp_path)
    assert search.search_content("SHIPS") != []


def test_empty_query_returns_nothing(vault, tmp_path):
    search, _ = make_search(vault, tmp_path)
    assert search.search_content("   ") == []
    assert search_filenames(vault, "") == []


def test_parse_query_splits_operators_from_words(vault):
    parsed = parse_query("timeline path:Projects file:alpha tag:#Home odd:thing")
    assert parsed.words == ("timeline", "odd:thing")
    assert parsed.paths == ("projects",)
    assert parsed.files == ("alpha",)
    assert parsed.tags == ("home",)


def test_path_operator_narrows_content_hits(vault, tmp_path):
    search, _ = make_search(vault, tmp_path)
    hits = search.search_content("meeting path:personal")
    assert [h.path for h in hits] == ["Personal/Meeting Notes.md"]


def test_file_operator_matches_the_filename_only(vault, tmp_path):
    search, _ = make_search(vault, tmp_path)
    assert [h.path for h in search.search_content("file:alpha")] == ["Projects/Alpha.md"]


def test_tag_operator_uses_the_graph_tags(vault, tmp_path):
    search, graph = make_search(vault, tmp_path)
    assert [h.path for h in search.search_content("tag:home", graph.note_tags)] == ["Index.md"]


def test_tag_operator_matches_nested_children(vault, tmp_path):
    search, graph = make_search(vault, tmp_path)
    assert [h.path for h in search.search_content("tag:project", graph.note_tags)] == ["Index.md"]


def test_tag_operator_without_tags_matches_nothing(vault, tmp_path):
    search, _ = make_search(vault, tmp_path)
    assert search.search_content("tag:home", None) == []


def test_filter_only_query_returns_hits_without_snippets(vault, tmp_path):
    search, _ = make_search(vault, tmp_path)
    hits = search.search_content("path:projects")
    assert hits and all(h.snippet == "" for h in hits)
    assert all(h.path.startswith("Projects/") for h in hits)


def test_hostile_query_text_never_reaches_fts_syntax(vault, tmp_path):
    search, _ = make_search(vault, tmp_path)
    for hostile in ('"broken', "a NEAR b", "col:x AND y", "((("):
        search.search_content(hostile)


def test_excluded_folders_rank_behind_rather_than_disappear():
    """Obsidian de-emphasises its excluded files; a dropped result is a different
    setting than the one that was chosen."""
    hits = [
        SearchHit(path="Archive/Old.md"),
        SearchHit(path="Notes/Live.md"),
        SearchHit(path="Archive/Older.md"),
        SearchHit(path="Notes/Newer.md"),
    ]
    ranked = demote(hits, {"Archive"})
    assert [hit.path for hit in ranked] == [
        "Notes/Live.md",
        "Notes/Newer.md",
        "Archive/Old.md",
        "Archive/Older.md",
    ]


def test_demotion_keeps_the_index_order_within_each_group():
    hits = [SearchHit(path=f"Notes/{n}.md") for n in "abc"]
    assert [hit.path for hit in demote(hits, {"Archive"})] == [hit.path for hit in hits]


def test_a_vault_that_excludes_nothing_is_left_alone():
    hits = [SearchHit(path="Archive/Old.md"), SearchHit(path="Notes/Live.md")]
    assert demote(hits, set()) == hits
