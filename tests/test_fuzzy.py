"""The fuzzy quick-open matcher: subsequences, ranking, and non-matches."""

from solander.core.fuzzy import (
    INSIDE_NAME,
    INSIDE_PATH,
    SCATTERED,
    WORD_IN_NAME,
    fuzzy_filenames,
    fuzzy_match,
    match_kind,
)

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


def test_a_word_in_the_name_beats_the_same_letters_scattered():
    """`brief` put `Brie Moffett` above `…-executive-brief` until matches were classed."""
    paths = [
        "People/Brie Moffett.md",
        "Personal/Bloodborne Advice for Soulsborne Veterans.md",
        "Briefs/order-fulfilment-and-demand-executive-brief.md",
    ]
    ranked = [match.path for match in fuzzy_filenames(paths, "brief")]
    assert ranked[0].endswith("executive-brief.md")


def test_a_date_in_a_filename_finds_the_note_named_after_it():
    """Every note mentioning 2026-09-04 matched `26904` as a subsequence, and outscored it."""
    paths = [
        "Features/2026-09-04-web-and-portable.md",
        "Features/2026-09-04-reading-companion.md",
        "Journal/2026/09/26904-notes.md",
    ]
    assert fuzzy_filenames(paths, "26904")[0].path.endswith("26904-notes.md")


def test_how_a_match_was_made_is_what_orders_it():
    whole = "notes/executive-brief.md"
    inside = "notes/briefing.md"
    folder = "brief/notes/something.md"
    scattered = "notes/Brie Moffett.md"
    assert match_kind("brief", whole) == WORD_IN_NAME
    assert match_kind("brief", inside) == INSIDE_NAME
    assert match_kind("brief", folder) == INSIDE_PATH
    assert match_kind("brief", scattered) == SCATTERED
    ranked = [m.path for m in fuzzy_filenames([scattered, folder, inside, whole], "brief")]
    assert ranked == [whole, inside, folder, scattered]
