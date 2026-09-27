"""A native local-graph pane: the current note and its neighbors, drawn with cairo."""

import math
import weakref

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk, Pango, PangoCairo

from ..core.graph import describe_neighbors, neighbor_phrase

NODE_RADIUS = 7.0
CENTER_RADIUS = 10.0
LABEL_MAX_CHARS = 18
HIT_RADIUS = 16.0


def _call(view_ref, name, *args):
    view = view_ref()
    if view is not None:
        getattr(view, name)(*args)


def _key(view_ref, keyval: int) -> bool:
    view = view_ref()
    return view.on_key(keyval) if view is not None else False


class LocalGraphView:
    """Draws one note's neighborhood as a radial graph; clicking a node opens it.

    The widget owns no vault state: the window hands it (center, neighbors)
    whenever the current note or the graph changes. Without a pointer, the arrow
    keys move between the linked notes and Enter opens one; a screen reader gets
    the whole neighborhood as text, and each move is announced.
    """

    def __init__(self, on_activate):
        self.on_activate = on_activate
        self.center = ""
        self.neighbors: list[tuple[str, str]] = []
        self._positions: list[tuple[float, float, str]] = []
        self.selected = -1
        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True, focusable=True)
        self._describe()
        # Bound-method callbacks would cycle area → callback → self → area, so
        # the widget's release would fall to the GC, which may run on the sync
        # thread, and a GTK object finalized off the main loop aborts the app.
        view = weakref.ref(self)
        self.area.set_draw_func(lambda area, cr, w, h: _call(view, "_draw", area, cr, w, h))
        click = Gtk.GestureClick()
        click.connect("released", lambda _g, n, x, y: _call(view, "_on_click", None, n, x, y))
        self.area.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, keyval, _code, _state: _key(view, keyval))
        self.area.add_controller(keys)
        focus = Gtk.EventControllerFocus()
        focus.connect("enter", lambda _c: _call(view, "_redraw"))
        focus.connect("leave", lambda _c: _call(view, "_redraw"))
        self.area.add_controller(focus)

    def show_note(self, center: str, neighbors: list[tuple[str, str]]) -> None:
        """Points the pane at a note and its neighbor list, then redraws."""
        self.center = center
        self.neighbors = neighbors
        self.selected = -1
        self._describe()
        self.area.queue_draw()

    def _describe(self) -> None:
        name, listed = describe_neighbors(self.center, self.neighbors)
        self.area.update_property(
            [Gtk.AccessibleProperty.LABEL, Gtk.AccessibleProperty.DESCRIPTION], [name, listed]
        )

    def _redraw(self) -> None:
        self.area.queue_draw()

    def on_key(self, keyval: int) -> bool:
        """Moves between the linked notes, or opens the selected one."""
        count = len(self.neighbors)
        if not count:
            return False
        if keyval in (Gdk.KEY_Right, Gdk.KEY_Down):
            self._select((self.selected + 1) % count)
        elif keyval in (Gdk.KEY_Left, Gdk.KEY_Up):
            self._select((self.selected - 1) % count if self.selected >= 0 else count - 1)
        elif keyval == Gdk.KEY_Home:
            self._select(0)
        elif keyval == Gdk.KEY_End:
            self._select(count - 1)
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            if self.selected < 0:
                return False
            self.on_activate(self.neighbors[self.selected][0])
        else:
            return False
        return True

    def _select(self, index: int) -> None:
        self.selected = index
        rel, direction = self.neighbors[index]
        self.area.announce(
            neighbor_phrase(rel, direction, index + 1, len(self.neighbors)),
            Gtk.AccessibleAnnouncementPriority.MEDIUM,
        )
        self.area.queue_draw()

    def _on_click(self, _gesture, _n_press, x: float, y: float) -> None:
        best = None
        best_distance = HIT_RADIUS
        for node_x, node_y, path in self._positions:
            distance = math.hypot(x - node_x, y - node_y)
            if distance < best_distance:
                best = path
                best_distance = distance
        if best and best != self.center:
            self.on_activate(best)

    def _draw(self, area, cr, width, height) -> None:
        self._positions = []
        if not self.center:
            return
        style = area.get_style_context()
        fg = style.get_color()
        # The theme's own accent, looked up rather than written down: this held
        # the old identity's gold and stayed gold in all fourteen themes.
        found, accent = style.lookup_color("accent_color")
        if not found:
            accent = fg
        center_x, center_y = width / 2, height / 2
        count = len(self.neighbors)
        ring = max(70.0, min(width, height) / 2 - 70.0)
        layout = Pango.Layout.new(area.get_pango_context())
        layout.set_font_description(Pango.FontDescription("Sans 8"))

        positions = []
        for index, (path, direction) in enumerate(self.neighbors):
            angle = 2 * math.pi * index / max(count, 1) - math.pi / 2
            node_x = center_x + ring * math.cos(angle)
            node_y = center_y + ring * math.sin(angle)
            positions.append((node_x, node_y, path, direction))

        cr.set_line_width(1.2)
        for node_x, node_y, _path, direction in positions:
            alpha = 0.55 if direction == "both" else 0.3
            cr.set_source_rgba(fg.red, fg.green, fg.blue, alpha)
            cr.move_to(center_x, center_y)
            cr.line_to(node_x, node_y)
            cr.stroke()

        for node_x, node_y, path, direction in positions:
            if direction == "both":
                cr.set_source_rgba(accent.red, accent.green, accent.blue, 0.9)
            elif direction == "in":
                cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.75)
            else:
                cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.45)
            cr.arc(node_x, node_y, NODE_RADIUS, 0, 2 * math.pi)
            cr.fill()
            if self.area.has_focus() and self._is_selected(path):
                # The keyboard's place, drawn as a ring rather than a colour.
                cr.set_source_rgba(accent.red, accent.green, accent.blue, 1.0)
                cr.set_line_width(2.0)
                cr.arc(node_x, node_y, NODE_RADIUS + 4, 0, 2 * math.pi)
                cr.stroke()
                cr.set_line_width(1.2)
            self._positions.append((node_x, node_y, path))
            self._label(cr, layout, fg, path, node_x, node_y + NODE_RADIUS + 2)

        cr.set_source_rgba(accent.red, accent.green, accent.blue, 1.0)
        cr.arc(center_x, center_y, CENTER_RADIUS, 0, 2 * math.pi)
        cr.fill()
        self._positions.append((center_x, center_y, self.center))
        self._label(cr, layout, fg, self.center, center_x, center_y + CENTER_RADIUS + 2, bold=True)

    def _is_selected(self, path: str) -> bool:
        return 0 <= self.selected < len(self.neighbors) and self.neighbors[self.selected][0] == path

    def _label(self, cr, layout, fg, path: str, x: float, y: float, bold: bool = False) -> None:
        stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if len(stem) > LABEL_MAX_CHARS:
            stem = stem[: LABEL_MAX_CHARS - 1] + "…"
        layout.set_text(stem, -1)
        weight = Pango.Weight.BOLD if bold else Pango.Weight.NORMAL
        description = Pango.FontDescription("Sans 8")
        description.set_weight(weight)
        layout.set_font_description(description)
        text_width, _text_height = layout.get_pixel_size()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.85)
        cr.move_to(x - text_width / 2, y)
        PangoCairo.show_layout(cr, layout)
