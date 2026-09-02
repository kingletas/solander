"""Themes: one identity per theme, the default one untouched, and every one legible."""

import re

from solander.core.palettes import PALETTES, contrast_ratio, mix, readable
from solander.core.render import _asset_css, build_page
from solander.core.session import SessionState
from solander.core.themes import (
    DEFAULT_THEME,
    THEMES,
    page_id,
    page_tokens,
    theme_by_key,
    variant_for,
)

AA = 4.5
"""WCAG AA for normal text. Every colour that carries words answers to it."""

TEXT_TOKENS = (
    "--fg",
    "--muted",
    "--accent",
    "--gold",
    "--missing",
    "--arc-hot",
    "--arc-second",
    "--arc-danger",
    "--arc-warning",
    "--arc-success",
    "--arc-info",
)


def tokens_of(palette) -> dict[str, str]:
    return dict(re.findall(r"(--[a-z-]+): (#[0-9a-f]{6});", page_tokens(palette)))


# -- the registry ---------------------------------------------------------


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


# -- the archive family ---------------------------------------------------


def test_every_palette_becomes_a_dark_only_theme_in_the_family():
    for palette in PALETTES:
        theme = theme_by_key(palette.key)
        assert theme.family == "Archive"
        assert theme.dark_only
        # Asking for light returns the only variant there is, rather than nothing.
        assert theme.variant(dark=False) is theme.variant(dark=True)
        classes = theme.variant(dark=True).body_classes.split()
        assert classes == ["theme-dark", "theme-archive", f"theme-{palette.key}"]


def test_the_family_shares_one_stylesheet_and_differs_only_in_tokens():
    sheets = {theme_by_key(p.key).variant(dark=True).stylesheet for p in PALETTES}
    assert sheets == {"theme-archive.css"}
    token_blocks = {theme_by_key(p.key).variant(dark=True).tokens for p in PALETTES}
    assert len(token_blocks) == len(PALETTES)


def test_an_archive_page_carries_the_shared_rules_and_its_own_palette():
    page = build_page("<p>x</p>", "Note", "corrosion")
    assert "class='theme-dark theme-archive theme-corrosion'" in page
    assert "body.theme-archive" in page
    assert "body.theme-corrosion" in page
    assert "--arc-hot: #" in page
    assert ".theme-corrosion .highlight" in page


def test_one_theme_never_ships_another_theme_s_palette():
    page = build_page("<p>x</p>", "Note", "corrosion")
    assert "theme-blood-record" not in page
    for identifier in ("light", "dark"):
        atelier = build_page("<p>x</p>", "Note", identifier)
        assert "theme-archive" not in atelier
        assert "--arc-hot" not in atelier


def test_each_page_carries_only_its_own_syntax_palette():
    """The generated Pygments defs are the page's own; the others are not shipped."""
    light = build_page("", "Note", "light")
    assert ".theme-light .highlight .k" in light
    assert ".theme-dark .highlight .k" not in light


def test_the_family_never_reaches_paper():
    """Print has no dark mode: reader.css forces a light palette and must keep winning."""
    sheet = _asset_css("theme-archive.css")
    body = re.sub(r"/\*.*?\*/", "", sheet, flags=re.S)
    top_level = [
        line for line in body.splitlines() if line.strip() and not line.startswith((" ", "\t"))
    ]
    assert top_level == ["@media screen {", "}"]


def test_blood_record_keeps_the_palette_it_shipped_with():
    """It was released before the family existed; generalizing it must not restyle it.

    Its surfaces and its accent are exactly what shipped. The colours that carry text
    are not: three of them measured below AA on that ground, and the solver lifts them.
    """
    palette = next(p for p in PALETTES if p.key == "blood-record")
    tokens = tokens_of(palette)
    assert tokens["--bg"] == "#100d0d"
    assert tokens["--fg"] == "#e6ded0"
    assert tokens["--surface"] == "#1d1818"
    assert tokens["--border-strong"] == "#4b2020"
    assert tokens["--arc-accent"] == "#a51f1f"
    assert palette.ornament == "#92503a"
    assert tokens["--gold"] == palette.legible(palette.ornament)


# -- legibility, measured -------------------------------------------------


def test_the_contrast_helper_agrees_with_known_values():
    """A broken helper would pass every assertion written under it."""
    assert round(contrast_ratio("#ffffff", "#000000"), 2) == 21.0
    assert round(contrast_ratio("#777777", "#777777"), 2) == 1.0
    assert round(contrast_ratio("#ffffff", "#767676"), 1) == 4.5
    assert mix("#000000", "#ffffff", 0.5) == "#808080"
    assert readable("#111111", "#000000", 4.5, "#ffffff") != "#111111"


def test_every_colour_that_carries_words_clears_aa():
    for palette in PALETTES:
        tokens = tokens_of(palette)
        for name in TEXT_TOKENS:
            ratio = contrast_ratio(tokens[name], tokens["--bg"])
            assert ratio >= AA, f"{palette.key} {name} is {ratio:.2f} on its page"


def test_text_stays_legible_on_panels_as_well_as_the_page():
    for palette in PALETTES:
        tokens = tokens_of(palette)
        for name in ("--fg", "--muted"):
            ratio = contrast_ratio(tokens[name], tokens["--surface"])
            assert ratio >= AA, f"{palette.key} {name} is {ratio:.2f} on a panel"


def test_code_and_rail_labels_are_measured_against_their_own_grounds():
    for palette in PALETTES:
        tokens = tokens_of(palette)
        code = contrast_ratio(tokens["--arc-code-fg"], tokens["--arc-code-bg"])
        assert code >= AA, f"{palette.key} inline code is {code:.2f} on the code ground"
        label = contrast_ratio(palette.rail_label, palette.void)
        assert label >= AA, f"{palette.key} rail labels are {label:.2f} on the rail"
