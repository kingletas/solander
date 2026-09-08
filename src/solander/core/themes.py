"""The reader's visual themes: one identity per theme, in palettes rather than rules.

A theme owns three things — the page tokens the reading surface consumes, the GTK
colors the window chrome consumes, and the syntax palette for code. Layout lives in
`reader.css` and the chrome structure lives with the window; neither is per-theme.

Every theme is generated from a `Palette`, Stone included, so adding one is sixteen
colours and no rules — and no theme carries a hand-written block the others cannot.
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

from .palettes import PALETTES, STONE_DARK, STONE_LIGHT, Palette, mix

DEFAULT_THEME = "stone"
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

    vibe: str = ""
    """What the theme is going for, in the words the chooser shows under its name."""

    paper: str = ""
    """The ground the theme reads on, for a swatch of it."""

    ink: str = ""
    """The colour text is set in, for a swatch of it."""

    mark: str = ""
    """The theme's own colour: the seal on a swatch of it."""

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


def page_tokens(palette: Palette, selector: str = "") -> str:
    """The custom properties one theme contributes; the rules it uses are shared.

    Screen only. Paper has no dark mode, reader.css states the palette a page is
    printed in, and a generated block is emitted after it — so a theme that reached
    print would win on source order and put the reader's ink on a black page.
    """
    p = palette
    return (
        "@media screen {\n"
        f"{selector or f'body.theme-{p.key}'} {{\n"
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
        "}\n}"
    )


def chrome(palette: Palette) -> str:
    """The GTK colours the shared chrome structure names; the structure never changes."""
    p = palette
    return (
        f"@define-color accent_bg_color {p.accent};\n"
        f"@define-color accent_fg_color {p.on_accent};\n"
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
        f"@define-color rail_accent {p.legible(p.hot, p.void)};\n"
        f"@define-color canvas_muted {p.muted};\n"
        # Stone separates its surfaces by hairline rather than by value, so the
        # lines are named colours instead of a wash of white over whatever is behind.
        f"@define-color hairline {p.line};\n"
        f"@define-color hairline_strong {p.line_strong};\n"
        f"@define-color accent_soft {mix(p.accent, p.bg, 0.86)};\n"
        f"@define-color rail_soft {mix(p.accent, p.void, 0.84)};\n"
        f"@define-color rail_raised {mix(p.surface, p.void, 0.35)};\n"
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


def _stone_variant(palette: Palette, mode: str) -> Variant:
    """One half of Stone: the house palette worn on the page the app already names."""
    return Variant(
        page_id=mode,
        body_classes=f"theme-{mode}",
        highlight_scope=f".theme-{mode}",
        chrome=chrome(palette),
        highlight=highlight_style(palette),
        tokens=page_tokens(palette, f"body.theme-{mode}"),
    )


def _archive_theme(palette: Palette) -> Theme:
    """Wraps one palette as a selectable theme; every rule it uses is shared."""
    return Theme(
        key=palette.key,
        label=palette.label,
        family="Archive",
        vibe=palette.vibe,
        paper=palette.bg,
        ink=palette.text,
        mark=palette.accent,
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


STONE = Theme(
    key="stone",
    label="Stone",
    family="Stone",
    vibe=STONE_LIGHT.vibe,
    paper=STONE_LIGHT.bg,
    ink=STONE_LIGHT.text,
    mark=STONE_LIGHT.accent,
    variants={
        # `light` and `dark` are the page identifiers the whole app is written
        # against: the renderer's default, the fallback for an unknown page, and
        # the body classes reader.css states its base rules on. Stone fills them.
        "light": _stone_variant(STONE_LIGHT, "light"),
        "dark": _stone_variant(STONE_DARK, "dark"),
    },
)

THEMES: dict[str, Theme] = {STONE.key: STONE}
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
