"""The paged reading surface: a chapter printed to real pages, turned like leaves.

WebKit's print pipeline does the pagination — exact line breaks, no JavaScript —
and Poppler draws each page. This widget shows one page at a time, slides
between them, and asks the window for the neighboring chapter at either cover.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, GObject, Gtk

TURN_MS = 300


class BookPagedView(Gtk.Box):
    """One printed page at a time, with e-reader turning.

    The page sits on an opaque desk with the place indicator in its own strip
    below — the indicator can never overlap the page's text.
    """

    __gsignals__ = {
        "turn-chapter": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.document = None
        self.index = 0
        self.count = 0
        self._desk = "#e8dcc0"
        self._current_texture = None
        self._desk_provider = Gtk.CssProvider()
        self.get_style_context().add_provider(
            self._desk_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.add_css_class("book-desk")

        self.page_picture = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN)
        self.page_area = Gtk.Overlay(vexpand=True, hexpand=True)
        self.page_area.set_child(self.page_picture)
        self.append(self.page_area)

        self.indicator = Gtk.Label()
        self.indicator.add_css_class("book-indicator")
        self.indicator.set_halign(Gtk.Align.CENTER)
        self.indicator.set_margin_top(4)
        self.indicator.set_margin_bottom(6)
        self.append(self.indicator)

        self.binding = Gtk.Label(label="Laying out the pages…")
        self.binding.add_css_class("book-indicator")
        self.binding.set_halign(Gtk.Align.CENTER)
        self.binding.set_valign(Gtk.Align.CENTER)
        self.binding.set_visible(False)
        self.page_area.add_overlay(self.binding)

        # An e-reader's tap zones: the left third turns back, the rest turns on.
        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)
        self.set_focusable(True)
        self.connect("notify::scale-factor", lambda *_: self._refresh())
        self.set_desk(self._desk)

    def set_desk(self, color: str) -> None:
        self._desk = color
        self._desk_provider.load_from_string(
            f".book-desk {{ background-color: {color}; }}"
        )

    def show_binding(self, on: bool) -> None:
        self.binding.set_visible(on)

    def load(self, pdf_path, direction: int = 1, at_end: bool = False) -> bool:
        """Opens a printed chapter and shows its first (or last) page."""
        gi.require_version("Poppler", "0.18")
        from gi.repository import Gio, Poppler

        try:
            uri = Gio.File.new_for_path(str(pdf_path)).get_uri()
            self.document = Poppler.Document.new_from_file(uri, None)
        except GLib.Error:
            self.document = None
            return False
        self.count = self.document.get_n_pages()
        if self.count <= 0:
            return False
        self.index = self.count - 1 if at_end else 0
        self.show_binding(False)
        self._show(self.index, direction, animate=True)
        return True

    def set_place(self, text: str) -> None:
        self._place = text
        self._update_indicator()

    def turn(self, delta: int) -> None:
        """Turns a page; past either cover, asks for the neighboring chapter."""
        if self.document is None:
            return
        target = self.index + delta
        if target < 0:
            self.emit("turn-chapter", -1)
            return
        if target >= self.count:
            self.emit("turn-chapter", 1)
            return
        self.index = target
        self._show(target, delta, animate=True)

    def _on_click(self, _gesture, _n, x, _y) -> None:
        width = self.get_width() or 1
        self.turn(-1 if x < width / 3 else 1)

    def _refresh(self) -> None:
        if self.document is not None:
            self._show(self.index, 1, animate=False)

    def _update_indicator(self) -> None:
        place = getattr(self, "_place", "")
        page = f"page {self.index + 1} of {self.count}" if self.count else ""
        joined = " · ".join(part for part in (place, page) if part)
        self.indicator.set_label(joined)

    def _render(self, index: int):
        import cairo

        page = self.document.get_page(index)
        page_w, page_h = page.get_size()
        widget_w = max(self.page_area.get_width(), 1)
        widget_h = max(self.page_area.get_height(), 1)
        hidpi = self.get_scale_factor() or 1
        scale = min(widget_w / page_w, widget_h / page_h) * hidpi
        pixel_w, pixel_h = max(int(page_w * scale), 1), max(int(page_h * scale), 1)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, pixel_w, pixel_h)
        context = cairo.Context(surface)
        context.scale(scale, scale)
        context.set_source_rgb(1, 1, 1)
        context.paint()
        page.render(context)
        surface.flush()
        data = bytes(surface.get_data())
        return Gdk.MemoryTexture.new(
            pixel_w, pixel_h, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,
            GLib.Bytes.new(data), surface.get_stride(),
        )

    def _show(self, index: int, direction: int, animate: bool) -> None:
        old_texture = self._current_texture
        texture = self._render(index)
        self._current_texture = texture
        self.page_picture.set_paintable(texture)
        self._update_indicator()
        if animate and old_texture is not None:
            self._slide_away(old_texture, direction)

    def _slide_away(self, old_texture, direction: int) -> None:
        """The outgoing page slides off over the new one, like a turned leaf."""
        width, height = self.page_area.get_width(), self.page_area.get_height()
        if width <= 0 or height <= 0:
            return
        old_picture = Gtk.Picture.new_for_paintable(old_texture)
        old_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        old_picture.set_size_request(width, height)
        holder = Gtk.Fixed()
        holder.set_can_target(False)
        holder.put(old_picture, 0, 0)
        self.page_area.add_overlay(holder)

        def frame(value):
            offset = -value * width if direction > 0 else value * width
            holder.move(old_picture, offset, 0)
            old_picture.set_opacity(1.0 - value * 0.15)

        target = Adw.CallbackAnimationTarget.new(frame)
        animation = Adw.TimedAnimation.new(holder, 0.0, 1.0, TURN_MS, target)
        animation.set_easing(Adw.Easing.EASE_OUT_CUBIC)
        animation.connect("done", lambda *_: self.page_area.remove_overlay(holder))
        animation.play()
        self._turn_animation = animation
