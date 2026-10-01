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


def ranked_search(tmp_path, notes: dict[str, str]):
    """A search over a small vault of the given notes, built through the real index."""
    from solander.core.vault import Vault

    root = tmp_path / "ranking"
    for rel, text in notes.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    vault = Vault.open(root)
    search, graph = make_search(vault, tmp_path)
    return search, graph


def test_a_note_is_found_by_its_own_name(tmp_path):
    search, _ = ranked_search(
        tmp_path,
        {
            "Kubernetes.md": "Clusters, pods and deployments.",
            "Daily/Mon.md": "Read about kubernetes.",
        },
    )
    assert [hit.path for hit in search.search_content("kubernetes")][0] == "Kubernetes.md"


def test_a_note_named_for_the_word_outranks_a_one_line_mention(tmp_path):
    search, _ = ranked_search(
        tmp_path,
        {
            "Inbox/stub.md": "kafka",
            "Guides/Kafka Guide.md": "Kafka topics. Kafka partitions. " * 3
            + "Consumers and producers. " * 20,
        },
    )
    assert [hit.path for hit in search.search_content("kafka")][0] == "Guides/Kafka Guide.md"


def test_the_exact_word_outranks_words_it_begins(tmp_path):
    search, _ = ranked_search(
        tmp_path,
        {
            "Shop/Catalogue.md": "The catalogue lists every category. "
            "Catalogue pages and category pages.",
            "Pets/Notes.md": "Our cat sleeps all day.",
        },
    )
    assert [hit.path for hit in search.search_content("cat")][0] == "Pets/Notes.md"


def test_a_filter_finds_its_note_however_many_notes_mention_the_word(tmp_path):
    notes = {f"standups/{n:04}.md": "standup notes " * 5 for n in range(1100)}
    notes["journal/2026-02-02.md"] = "a short standup"
    search, _ = ranked_search(tmp_path, notes)
    assert [hit.path for hit in search.search_content("path:journal standup")] == [
        "journal/2026-02-02.md"
    ]


def test_a_property_operator_keeps_its_spaces_and_case():
    query = parse_query("[Project:Garden Shed] standup [status]")
    assert query.words == ("standup",)
    assert query.properties == (("project", "garden shed"), ("status", None))
    assert not query.empty


def test_a_bare_bracket_is_a_word_not_an_operator():
    assert parse_query("[] [:x]").properties == ()


def test_search_by_property_value_and_presence(vault, vault_dir, tmp_path):
    (vault_dir / "Projects" / "Beta.md").write_text(
        "---\nproject: Garden Shed\nstatus: open\n---\n# Beta\n\nstandup notes\n"
    )
    (vault_dir / "Projects" / "Gamma.md").write_text(
        "---\nproject:\n  - Kitchen\n  - Garden Shed\n---\n# Gamma\n\nstandup notes\n"
    )
    (vault_dir / "Projects" / "Delta.md").write_text(
        "---\nproject: Kitchen\n---\n# Delta\n\nstandup notes\n"
    )
    vault.reindex()
    search, graph = make_search(vault, tmp_path)

    def paths(query):
        return sorted(h.path for h in search.search_content(query, graph.note_tags, graph.props))

    assert paths("[project:garden shed]") == ["Projects/Beta.md", "Projects/Gamma.md"]
    assert paths("[project:Garden Shed] standup") == ["Projects/Beta.md", "Projects/Gamma.md"]
    assert paths("[status]") == ["Projects/Beta.md"]
    assert paths("[project:Kitchen] [status]") == []
    assert paths("[nowhere]") == []
