"""A sidebar beside content, with a divider a person can drag.

`Adw.OverlaySplitView` sizes its sidebar from a fraction and a pair of ceilings,
which is a layout the window decides and the reader cannot argue with. A pane is
a preference — how much of the screen an outline is worth is not something this
file knows — so the divider is a handle, and where it is left is session state
like every other pane preference.

The `show-sidebar` property is carried so the window's actions, its shortcuts and
its saved session all keep speaking about panes the way they did.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GObject, Gtk

# The narrowest a pane may be dragged. Below this the labels in it are ellipses
# and the handle is easier to lose than to find.
MIN_PANE_WIDTH = 150


class SplitPane(Gtk.Paned):
    """Content and one sidebar, divided where the person put the divider."""

    show_sidebar = GObject.Property(type=bool, default=True)

    def __init__(
        self,
        sidebar: Gtk.Widget,
        content: Gtk.Widget,
        at_end: bool = False,
        width: int = 260,
        minimum: int = MIN_PANE_WIDTH,
    ):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.sidebar = sidebar
        self.at_end = at_end
        self.minimum = minimum
        self._wanted = max(width, minimum)
        sidebar.set_size_request(minimum, -1)
        if at_end:
            self.set_start_child(content)
            self.set_end_child(sidebar)
            self.set_resize_start_child(True)
            self.set_shrink_start_child(True)
            self.set_resize_end_child(False)
            self.set_shrink_end_child(False)
        else:
            self.set_start_child(sidebar)
            self.set_end_child(content)
            self.set_resize_start_child(False)
            self.set_shrink_start_child(False)
            self.set_resize_end_child(True)
            self.set_shrink_end_child(True)
        self.connect("notify::show-sidebar", self._shown)
        self.connect("notify::position", self._dragged)
        self._applied = False

    # -- where the divider goes --------------------------------------------

    def do_size_allocate(self, width: int, height: int, baseline: int) -> None:
        """Puts the remembered width in on the first allocation, and never again.

        A pane asked for a position before it has a size of its own is asked to
        divide nothing, and a sidebar at the end has no position at all until
        there is a width to subtract it from — so the remembered width waits for
        an allocation rather than being set at construction.
        """
        Gtk.Paned.do_size_allocate(self, width, height, baseline)
        self._apply()

    # -- how wide the sidebar is -------------------------------------------

    @property
    def sidebar_width(self) -> int:
        """The sidebar's own width, whichever side of the divider it is on."""
        if not self._applied:
            return self._wanted
        position = self.get_position()
        return self.get_width() - position if self.at_end else position

    def set_sidebar_width(self, width: int) -> None:
        """Puts the divider where a width says, once there is a pane to put it in."""
        self._wanted = max(int(width), self.minimum)
        self._applied = False
        self._apply()

    def _apply(self) -> None:
        total = self.get_width()
        if self._applied or total <= 1:
            return
        self._applied = True
        self.set_position(total - self._wanted if self.at_end else self._wanted)

    def _dragged(self, *_args) -> None:
        if self._applied and self.get_width() > 1:
            self._wanted = max(self.sidebar_width, self.minimum)

    # -- whether it is showing ---------------------------------------------

    def _shown(self, *_args) -> None:
        self.sidebar.set_visible(self.get_show_sidebar())

    def get_sidebar(self) -> Gtk.Widget:
        """The widget this pane holds beside its content."""
        return self.sidebar

    def get_show_sidebar(self) -> bool:
        return bool(self.get_property("show-sidebar"))

    def set_show_sidebar(self, showing: bool) -> None:
        self.set_property("show-sidebar", bool(showing))
