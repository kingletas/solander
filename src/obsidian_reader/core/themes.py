"""The reader's visual themes: one identity per theme, in palettes rather than rules.

A theme owns three things — the page tokens the reading surface consumes, the GTK
colors the window chrome consumes, and the syntax palette for code. Layout lives in
`reader.css` and the chrome structure lives with the window; neither is per-theme.
"""

from dataclasses import dataclass, field

from pygments.style import Style
from pygments.token import (
    Comment,
    Error,
    Generic,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Token,
)

DEFAULT_THEME = "atelier"


class BloodRecordStyle(Style):
    """Syntax colors for Blood Record: bone and copper on blackened crimson."""

    background_color = "#090707"
    styles = {
        Token: "#c9c0b1",
        Comment: "italic #665f56",
        Keyword: "bold #d52b2b",
        Keyword.Type: "#c1843d",
        Name: "#d9cdbb",
        Name.Builtin: "#c1843d",
        Name.Class: "bold #d9cdbb",
        Name.Function: "#d9cdbb",
        Name.Attribute: "#b87862",
        Name.Tag: "#d52b2b",
        Name.Variable: "#b87862",
        String: "#c17857",
        String.Escape: "#d9826c",
        Number: "#c1843d",
        Operator: "#9c8f83",
        Punctuation: "#8a8078",
        Error: "bold #ff3b30",
        Generic.Deleted: "#d52b2b",
        Generic.Inserted: "#78966a",
        Generic.Heading: "bold #d9cdbb",
        Generic.Emph: "italic",
        Generic.Strong: "bold",
    }


@dataclass(frozen=True)
class Variant:
    """One theme in one appearance mode: what the page wears and what the chrome wears."""

    page_id: str
    body_classes: str
    highlight_scope: str
    chrome: str
    highlight: object = "default"
    stylesheet: str = ""
    chrome_extra: str = ""


@dataclass(frozen=True)
class Theme:
    """A selectable identity, offering one variant per appearance mode it supports."""

    key: str
    label: str
    variants: dict[str, Variant] = field(default_factory=dict)

    @property
    def dark_only(self) -> bool:
        """A theme with a single dark variant; the light/dark choice does not apply to it."""
        return tuple(self.variants) == ("dark",)

    def variant(self, dark: bool) -> Variant:
        """Returns the variant for the requested mode, or the only one the theme has."""
        wanted = "dark" if dark else "light"
        if wanted in self.variants:
            return self.variants[wanted]
        return next(iter(self.variants.values()))


# Two surfaces, one identity: a deep sepia rail beside the parchment canvas,
# with the header flattened into the canvas rather than a third tint.
_ATELIER_LIGHT_CHROME = """
@define-color accent_bg_color #1c4e9c;
@define-color accent_fg_color #ffffff;
@define-color accent_color #1c4e9c;
@define-color window_bg_color #f9f4e7;
@define-color window_fg_color #2b2620;
@define-color headerbar_bg_color #f9f4e7;
@define-color headerbar_fg_color #2b2620;
@define-color view_bg_color #f9f4e7;
@define-color view_fg_color #2b2620;
@define-color popover_bg_color #f6f0df;
@define-color popover_fg_color #2b2620;
@define-color dialog_bg_color #f6f0df;
@define-color dialog_fg_color #2b2620;
@define-color card_bg_color #f4eeda;
@define-color card_fg_color #2b2620;
@define-color rail_bg #2a2420;
@define-color rail_fg #d8d0c0;
@define-color rail_muted #97907f;
@define-color rail_accent #d0a44e;
@define-color canvas_muted #6f6455;
"""

_ATELIER_DARK_CHROME = """
@define-color accent_bg_color #5c84c4;
@define-color accent_fg_color #ffffff;
@define-color accent_color #8fb0e8;
@define-color window_bg_color #1c1a16;
@define-color window_fg_color #d9d2c2;
@define-color headerbar_bg_color #1c1a16;
@define-color headerbar_fg_color #d9d2c2;
@define-color view_bg_color #1c1a16;
@define-color view_fg_color #d9d2c2;
@define-color popover_bg_color #2a261e;
@define-color popover_fg_color #d9d2c2;
@define-color dialog_bg_color #2a261e;
@define-color dialog_fg_color #d9d2c2;
@define-color card_bg_color #262218;
@define-color card_fg_color #d9d2c2;
@define-color rail_bg #16130f;
@define-color rail_fg #cfc7b6;
@define-color rail_muted #857d6d;
@define-color rail_accent #d0a44e;
@define-color canvas_muted #a29882;
"""

# Blackened iron either side of the record, oxidized copper for what is important,
# and the one hot red held back for the thing currently under the reader's hand.
_BLOOD_RECORD_CHROME = """
@define-color accent_bg_color #a51f1f;
@define-color accent_fg_color #f6ece4;
@define-color accent_color #d9826c;
@define-color window_bg_color #100d0d;
@define-color window_fg_color #e6ded0;
@define-color headerbar_bg_color #100d0d;
@define-color headerbar_fg_color #e6ded0;
@define-color view_bg_color #100d0d;
@define-color view_fg_color #e6ded0;
@define-color popover_bg_color #151111;
@define-color popover_fg_color #c9c0b1;
@define-color dialog_bg_color #151111;
@define-color dialog_fg_color #c9c0b1;
@define-color card_bg_color #171313;
@define-color card_fg_color #e6ded0;
@define-color rail_bg #0b0909;
@define-color rail_fg #c9c0b1;
@define-color rail_muted #938a7e;
@define-color rail_accent #d52b2b;
@define-color canvas_muted #938a7e;
"""

# The rail's labels stay dried blood; only the selected row is allowed the hot red,
# so a flagged document is the one thing on the rail that shouts.
_BLOOD_RECORD_CHROME_EXTRA = """
headerbar { border-bottom: 1px solid #2d1c1c; }
.reader-rail { border-right: 1px solid #352020; }
.reader-rail .rail-title,
.reader-rail .quick-heading,
.outline-panel .panel-heading { color: #8f302c; }
.reader-rail row:selected {
    background: linear-gradient(to right, alpha(#7f1717, 0.38), alpha(#7f1717, 0.08));
    box-shadow: inset 2px 0 0 #d52b2b;
    color: #f0e7d8;
}
.reader-rail row:hover { background: alpha(#d52b2b, 0.07); }
.reader-rail entry:focus-within { border-color: #a51f1f; }
.reader-rail .rail-separator { background: #352020; }
.navigation-sidebar row:selected { box-shadow: inset 2px 0 0 #d52b2b; }
.outline-panel row:hover, .outline-panel row:selected { color: #d9826c; }
scrollbar { background: #0b0909; }
scrollbar slider {
    background: #352020;
    border: none;
    border-radius: 0;
    min-width: 8px;
    min-height: 8px;
}
scrollbar slider:hover { background: #7f1717; }
scrollbar slider:active { background: #a51f1f; }
"""

ATELIER = Theme(
    key="atelier",
    label="Atelier",
    variants={
        "light": Variant(
            page_id="light",
            body_classes="theme-light",
            highlight_scope=".theme-light",
            chrome=_ATELIER_LIGHT_CHROME,
            highlight="default",
        ),
        "dark": Variant(
            page_id="dark",
            body_classes="theme-dark",
            highlight_scope=".theme-dark",
            chrome=_ATELIER_DARK_CHROME,
            highlight="monokai",
        ),
    },
)

BLOOD_RECORD = Theme(
    key="blood-record",
    label="Blood Record",
    variants={
        "dark": Variant(
            page_id="blood-record",
            # The dark class first, so every dark rule in reader.css is the base
            # this theme paints over rather than a second thing to restate.
            body_classes="theme-dark theme-blood-record",
            highlight_scope=".theme-blood-record",
            chrome=_BLOOD_RECORD_CHROME,
            highlight=BloodRecordStyle,
            stylesheet="theme-blood-record.css",
            chrome_extra=_BLOOD_RECORD_CHROME_EXTRA,
        ),
    },
)

THEMES: dict[str, Theme] = {theme.key: theme for theme in (ATELIER, BLOOD_RECORD)}

_BY_PAGE_ID: dict[str, Variant] = {
    variant.page_id: variant for theme in THEMES.values() for variant in theme.variants.values()
}


def theme_by_key(key: str) -> Theme:
    """Returns a theme by key; an unknown or dropped key falls back to the default."""
    return THEMES.get(key, THEMES[DEFAULT_THEME])


def page_id(theme_key: str, dark: bool) -> str:
    """Returns the page identifier a renderer is given for this theme and mode."""
    return theme_by_key(theme_key).variant(dark).page_id


def variant_for(page: str) -> Variant:
    """Returns the variant a page identifier names; unknown identifiers read as light."""
    return _BY_PAGE_ID.get(page, _BY_PAGE_ID["light"])
