"""Themes: one identity per theme, and the default one unchanged by the others."""

import re

from obsidian_reader.core.render import _asset_css, build_page
from obsidian_reader.core.session import SessionState
from obsidian_reader.core.themes import (
    DEFAULT_THEME,
    THEMES,
    page_id,
    theme_by_key,
    variant_for,
)


def test_the_default_theme_is_what_a_fresh_session_wears():
    assert SessionState().theme == DEFAULT_THEME
    assert DEFAULT_THEME in THEMES


def test_page_identifiers_are_unique_across_every_theme():
    ids = [v.page_id for theme in THEMES.values() for v in theme.variants.values()]
    assert len(ids) == len(set(ids))


def test_every_variant_declares_a_scope_matching_its_body_classes():
    for theme in THEMES.values():
        for variant in theme.variants.values():
            assert variant.highlight_scope.lstrip(".") in variant.body_classes.split()


def test_an_unknown_theme_key_falls_back_to_the_default():
    assert theme_by_key("no-such-theme").key == DEFAULT_THEME
    assert page_id("no-such-theme", dark=False) == "light"


def test_the_original_theme_still_answers_to_light_and_dark():
    assert page_id("atelier", dark=False) == "light"
    assert page_id("atelier", dark=True) == "dark"
    assert variant_for("light").body_classes == "theme-light"
    assert variant_for("dark").body_classes == "theme-dark"
    assert not theme_by_key("atelier").dark_only


def test_blood_record_is_dark_only_and_keeps_dark_as_its_base():
    theme = theme_by_key("blood-record")
    assert theme.dark_only
    # Asking for light returns the only variant there is, rather than nothing.
    assert theme.variant(dark=False) is theme.variant(dark=True)
    assert page_id("blood-record", dark=False) == "blood-record"
    assert variant_for("blood-record").body_classes.split() == [
        "theme-dark",
        "theme-blood-record",
    ]


def test_a_blood_record_page_carries_its_own_palette_and_syntax_scope():
    page = build_page("<p>x</p>", "Note", "blood-record")
    assert "class='theme-dark theme-blood-record'" in page
    assert "body.theme-blood-record" in page
    assert "--blood-hot: #d52b2b;" in page
    assert ".theme-blood-record .highlight" in page


def test_the_original_theme_carries_none_of_the_new_one():
    for identifier in ("light", "dark"):
        page = build_page("<p>x</p>", "Note", identifier)
        assert "theme-blood-record" not in page
        assert "--blood-hot" not in page


def test_each_page_carries_only_its_own_syntax_palette():
    """The generated Pygments defs are the page's own; the others are not shipped."""
    light = build_page("", "Note", "light")
    assert ".theme-light .highlight .k" in light
    assert ".theme-dark .highlight .k" not in light


def test_the_theme_never_reaches_paper():
    """Print has no dark mode: reader.css forces a light palette and must keep winning."""
    sheet = _asset_css("theme-blood-record.css")
    body = re.sub(r"/\*.*?\*/", "", sheet, flags=re.S)
    top_level = [
        line
        for line in body.splitlines()
        if line.strip() and not line.startswith((" ", "\t"))
    ]
    assert top_level == ["@media screen {", "}"]
    page = build_page("", "Note", "blood-record")
    assert page.index("@media screen") < page.index("body.theme-blood-record")
