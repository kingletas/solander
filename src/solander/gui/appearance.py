"""Choosing a theme by looking at it rather than by reading fourteen names.

A theme is a look, and a list of names asks a person to remember which look each
name belongs to. Every theme states the ground it reads on, the colour its text
is set in and its own mark, so the swatch is drawn from the theme itself and no
picture is kept anywhere.
"""

from math import pi

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from ..core.themes import THEMES

COLUMNS = 3

# Big enough to read the ground against the text, small enough that fourteen of
# them are one glance rather than a page.
SWATCH_WIDTH = 64
SWATCH_HEIGHT = 40

CSS = """
.theme-cell { padding: 4px 2px; border-radius: 8px; }
.theme-cell label { font-size: 0.86em; }
"""


def _color(value: str, alpha: float = 1.0) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.parse(value)
    rgba.alpha = alpha
    return rgba


def _rounded(context, width: float, height: float, radius: float) -> None:
    context.new_sub_path()
    context.arc(width - radius, radius, radius, -pi / 2, 0)
    context.arc(width - radius, height - radius, radius, 0, pi / 2)
    context.arc(radius, height - radius, radius, pi / 2, pi)
    context.arc(radius, radius, radius, pi, 3 * pi / 2)
    context.close_path()


class Swatch(Gtk.DrawingArea):
    """One theme drawn as the thing it themes: a page, a title, three lines of text.

    The tick is drawn here rather than laid over the top because a menu's own
    foreground is the colour of the menu, and half of these grounds are black.
    """

    def __init__(self, theme):
        super().__init__(
            content_width=SWATCH_WIDTH, content_height=SWATCH_HEIGHT, halign=Gtk.Align.CENTER
        )
        self.theme = theme
        self.selected = False
        self.set_draw_func(self._draw)

    def choose(self, selected: bool) -> None:
        self.selected = selected
        self.queue_draw()

    def _draw(self, _area, context, width, height) -> None:
        theme = self.theme
        _rounded(context, width, height, 6)
        Gdk.cairo_set_source_rgba(context, _color(theme.paper))
        context.fill_preserve()
        Gdk.cairo_set_source_rgba(context, _color(theme.ink, 0.30))
        context.set_line_width(1)
        context.stroke()

        margin = 9
        Gdk.cairo_set_source_rgba(context, _color(theme.mark))
        context.rectangle(margin, 9, (width - 2 * margin) * 0.55, 3)
        context.fill()
        Gdk.cairo_set_source_rgba(context, _color(theme.ink, 0.70))
        for row, fraction in enumerate((1.0, 0.86, 0.62)):
            context.rectangle(margin, 19 + row * 6, (width - 2 * margin) * fraction, 2)
        context.fill()
        if self.selected:
            self._tick(context, width)

    def _tick(self, context, width: float) -> None:
        """A mark in the theme's own ink, on a disc of its own paper."""
        centre_x, centre_y, radius = width - 12, 12, 9
        context.arc(centre_x, centre_y, radius, 0, 2 * pi)
        Gdk.cairo_set_source_rgba(context, _color(self.theme.mark))
        context.fill()
        Gdk.cairo_set_source_rgba(context, _color(self.theme.paper))
        context.set_line_width(2)
        context.set_line_cap(1)  # round
        context.move_to(centre_x - 4, centre_y)
        context.line_to(centre_x - 1, centre_y + 3.5)
        context.line_to(centre_x + 4.5, centre_y - 3.5)
        context.stroke()


class ThemeChooser(Gtk.Grid):
    """Every theme as a swatch of itself, with the one in force marked."""

    def __init__(self, current: str, on_chosen):
        super().__init__(column_spacing=4, row_spacing=2)
        for margin in ("top", "bottom", "start", "end"):
            getattr(self, f"set_margin_{margin}")(6)
        self.cells: dict[str, Gtk.ToggleButton] = {}
        self.swatches: dict[str, Swatch] = {}
        self._on_chosen = on_chosen
        self._settling = False
        first = None
        for index, (key, theme) in enumerate(THEMES.items()):
            cell = self._cell(key, theme, first)
            first = first or cell
            self.attach(cell, index % COLUMNS, index // COLUMNS, 1, 1)
            self.cells[key] = cell
        self.show(current)

    def _cell(self, key: str, theme, group) -> Gtk.ToggleButton:
        swatch = Swatch(theme)
        self.swatches[key] = swatch
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.append(swatch)
        box.append(Gtk.Label(label=theme.label, ellipsize=3, max_width_chars=14))

        cell = Gtk.ToggleButton(child=box)
        cell.add_css_class("flat")
        cell.add_css_class("theme-cell")
        cell.set_tooltip_text(theme.vibe or theme.label)
        if group is not None:
            cell.set_group(group)
        cell.connect("toggled", self._chosen, key)
        return cell

    def _chosen(self, cell: Gtk.ToggleButton, key: str) -> None:
        self.swatches[key].choose(cell.get_active())
        if cell.get_active() and not self._settling:
            self._on_chosen(key)

    def show(self, current: str) -> None:
        """Marks the theme in force, without reporting it back as a fresh choice."""
        self._settling = True
        for key, cell in self.cells.items():
            cell.set_active(key == current)
        self._settling = False
