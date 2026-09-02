"""The fuzzy quick-open matcher: subsequences, ranking, and non-matches."""

from solander.core.fuzzy import fuzzy_filenames, fuzzy_match

PATHS = [
    "Projects/Alpha.md",
    "Projects/Meeting Notes.md",
    "Personal/Meeting Notes.md",
    "Archive/alp-history.md",
]


def test_subsequence_matches_and_missing_letters_do_not():
    assert fuzzy_match("alp", "Projects/Alpha.md") is not None
    assert fuzzy_match("alpz", "Projects/Alpha.md") is None


def test_name_start_outranks_a_path_match():
    hits = fuzzy_filenames(PATHS, "alp")
    assert hits[0].path in ("Projects/Alpha.md", "Archive/alp-history.md")
    assert {h.path for h in hits[:2]} == {"Projects/Alpha.md", "Archive/alp-history.md"}


def test_initials_match_across_words():
    hits = fuzzy_filenames(PATHS, "pmn")
    assert any(h.path == "Personal/Meeting Notes.md" for h in hits)


def test_every_word_must_match():
    hits = fuzzy_filenames(PATHS, "meeting personal")
    assert [h.path for h in hits] == ["Personal/Meeting Notes.md"]


def test_empty_query_matches_nothing():
    assert fuzzy_filenames(PATHS, "  ") == []
