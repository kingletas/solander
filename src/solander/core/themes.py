"""The reader's visual themes: one identity per theme, in palettes rather than rules.

A theme owns three things — the page tokens the reading surface consumes, the GTK
colors the window chrome consumes, and the syntax palette for code. Layout lives in
`reader.css` and the chrome structure lives with the window; neither is per-theme.

Atelier is written out here because it is its own design. Every member of the Archive
family is generated from one `Palette`, so adding one is sixteen colours and no rules.
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

from .palettes import PALETTES, Palette, mix

DEFAULT_THEME = "atelier"
ARCHIVE_CLASS = "theme-archive"


@dataclass(frozen=True)
class Variant:
    """One theme in one appearance mode: what the page wears and what the chrome wears."""

    page_id: str
    body_classes: str
    highlight_scope: str
    chrome: str
    highlight: object = "default"
    stylesheet: str = ""
    tokens: str = ""
    chrome_extra: str = ""


@dataclass(frozen=True)
class Theme:
    """A selectable identity, offering one variant per appearance mode it supports."""

    key: str
    label: str
    variants: dict[str, Variant] = field(default_factory=dict)
    family: str = ""

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


def page_tokens(palette: Palette) -> str:
    """The custom properties one Archive theme contributes; the rules are shared."""
    p = palette
    return (
        f"body.theme-{p.key} {{\n"
        f"  --bg: {p.bg};\n"
        f"  --fg: {p.text};\n"
        f"  --muted: {p.legible(p.muted)};\n"
        f"  --border: {p.line};\n"
        f"  --border-strong: {p.line_strong};\n"
        f"  --surface: {p.surface};\n"
        f"  --accent: {p.legible(p.link)};\n"
        f"  --accent-soft: {mix(p.accent, p.bg, 0.82)};\n"
        f"  --gold: {p.legible(p.ornament)};\n"
        f"  --missing: {p.legible(p.danger)};\n"
        f"  --mark-bg: {mix(p.accent, p.bg, 0.45)};\n"
        f"  --arc-void: {p.void};\n"
        f"  --arc-deep: {p.deep};\n"
        f"  --arc-accent: {p.accent};\n"
        f"  --arc-hot: {p.legible(p.hot)};\n"
        f"  --arc-second: {p.legible(p.second)};\n"
        f"  --arc-bright: {p.bright};\n"
        f"  --arc-code-bg: {p.code_bg};\n"
        f"  --arc-code-fg: {p.legible(p.code_fg, p.code_bg)};\n"
        f"  --arc-danger: {p.legible(p.danger)};\n"
        f"  --arc-warning: {p.legible(p.warning)};\n"
        f"  --arc-success: {p.legible(p.success)};\n"
        f"  --arc-info: {p.legible(p.info)};\n"
        "}"
    )


def chrome(palette: Palette) -> str:
    """The GTK colours the shared chrome structure names; the structure never changes."""
    p = palette
    return (
        f"@define-color accent_bg_color {p.accent};\n"
        f"@define-color accent_fg_color {p.bright};\n"
        f"@define-color accent_color {p.legible(mix(p.link, p.text, 0.25))};\n"
        f"@define-color window_bg_color {p.bg};\n"
        f"@define-color window_fg_color {p.text};\n"
        f"@define-color headerbar_bg_color {p.bg};\n"
        f"@define-color headerbar_fg_color {p.text};\n"
        f"@define-color view_bg_color {p.bg};\n"
        f"@define-color view_fg_color {p.text};\n"
        f"@define-color popover_bg_color {mix(p.bg, p.surface, 0.45)};\n"
        f"@define-color popover_fg_color {mix(p.text, p.muted, 0.35)};\n"
        f"@define-color dialog_bg_color {mix(p.bg, p.surface, 0.45)};\n"
        f"@define-color dialog_fg_color {mix(p.text, p.muted, 0.35)};\n"
        f"@define-color card_bg_color {mix(p.bg, p.surface, 0.6)};\n"
        f"@define-color card_fg_color {p.text};\n"
        f"@define-color rail_bg {p.void};\n"
        f"@define-color rail_fg {mix(p.text, p.muted, 0.4)};\n"
        f"@define-color rail_muted {p.muted};\n"
        f"@define-color rail_accent {p.hot};\n"
        f"@define-color canvas_muted {p.muted};\n"
    )


def chrome_extra(palette: Palette) -> str:
    """The archive's own chrome: quiet labels, one flagged row, industrial scrollbars."""
    p = palette
    return f"""
headerbar {{ border-bottom: 1px solid {mix(p.line_strong, p.bg, 0.4)}; }}
.reader-rail {{ border-right: 1px solid {mix(p.line_strong, p.void, 0.3)}; }}
.reader-rail .rail-title,
.reader-rail .quick-heading,
.outline-panel .panel-heading {{ color: {p.rail_label}; }}
.reader-rail row:selected {{
    background: linear-gradient(to right, alpha({p.deep}, 0.38), alpha({p.deep}, 0.08));
    box-shadow: inset 2px 0 0 {p.hot};
    color: {p.bright};
}}
.reader-rail row:hover {{ background: alpha({p.hot}, 0.07); }}
.reader-rail entry:focus-within {{ border-color: {p.accent}; }}
.reader-rail .rail-separator {{ background: {mix(p.line_strong, p.void, 0.3)}; }}
.navigation-sidebar row:selected {{ box-shadow: inset 2px 0 0 {p.hot}; }}
.outline-panel row:hover, .outline-panel row:selected {{ color: {mix(p.link, p.text, 0.25)}; }}
scrollbar {{ background: {p.void}; }}
scrollbar slider {{
    background: {mix(p.deep, p.void, 0.45)};
    border: none;
    border-radius: 0;
    min-width: 8px;
    min-height: 8px;
}}
scrollbar slider:hover {{ background: {p.deep}; }}
scrollbar slider:active {{ background: {p.accent}; }}
"""


def highlight_style(palette: Palette) -> type[Style]:
    """Builds the syntax palette for one theme: evidence, in the theme's own colours."""
    p = palette
    ground = p.code_bg
    legible = lambda color: p.legible(color, ground)  # noqa: E731
    namespace = {
        "background_color": ground,
        "styles": {
            Token: legible(mix(p.text, p.muted, 0.25)),
            Comment: f"italic {legible(mix(p.muted, p.void, 0.45))}",
            Keyword: f"bold {legible(p.hot)}",
            Keyword.Type: legible(p.warning),
            Name: legible(mix(p.text, p.muted, 0.15)),
            Name.Builtin: legible(p.warning),
            Name.Class: f"bold {legible(mix(p.text, p.muted, 0.15))}",
            Name.Function: legible(mix(p.text, p.muted, 0.15)),
            Name.Attribute: legible(p.second),
            Name.Tag: legible(p.hot),
            Name.Variable: legible(p.second),
            String: legible(p.link),
            String.Escape: legible(p.code_fg),
            Number: legible(p.warning),
            Operator: legible(p.muted),
            Punctuation: legible(mix(p.muted, p.text, 0.15)),
            Error: f"bold {legible(p.danger)}",
            Generic.Deleted: legible(p.danger),
            Generic.Inserted: legible(p.success),
            Generic.Heading: f"bold {p.text}",
            Generic.Emph: "italic",
            Generic.Strong: "bold",
        },
    }
    name = "".join(part.capitalize() for part in palette.key.split("-")) + "Style"
    return type(Style)(name, (Style,), namespace)


def _archive_theme(palette: Palette) -> Theme:
    """Wraps one palette as a selectable theme; every rule it uses is shared."""
    return Theme(
        key=palette.key,
        label=palette.label,
        family="Archive",
        variants={
            "dark": Variant(
                page_id=palette.key,
                # The dark class first, so every dark rule in reader.css is the base
                # the family paints over, then the shared archive rules, then the
                # theme's own tokens.
                body_classes=f"theme-dark {ARCHIVE_CLASS} theme-{palette.key}",
                highlight_scope=f".theme-{palette.key}",
                chrome=chrome(palette),
                highlight=highlight_style(palette),
                stylesheet="theme-archive.css",
                tokens=page_tokens(palette),
                chrome_extra=chrome_extra(palette),
            ),
        },
    )


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

THEMES: dict[str, Theme] = {ATELIER.key: ATELIER}
for _palette in PALETTES:
    THEMES[_palette.key] = _archive_theme(_palette)

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
