"""An embedded PDF viewer: system Poppler renders pages into cairo, read-only.

Poppler's GIR bindings are an optional system package; when they are absent the
caller falls back to opening the file externally, and nothing here is reached.
"""

from pathlib import Path

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

try:
    gi.require_version("Poppler", "0.18")
    from gi.repository import Poppler
except (ImportError, ValueError):
    Poppler = None

MAX_PDF_PAGES = 1000
PAGE_GAP = 14
FIT_WIDTH = 840
MIN_SCALE = 0.4
MAX_SCALE = 4.0
SURFACE_CACHE = 12


def poppler_available() -> bool:
    """Reports whether the system Poppler GIR bindings are importable."""
    return Poppler is not None


class PdfWindow(Adw.Window):
    """One PDF, rendered page by page on demand; the file is never written."""

    def __init__(self, path: Path, parent):
        super().__init__(title=path.name, transient_for=None)
        self.set_default_size(920, 980)
        self.path = path
        self.document = None
        self.scale = 1.0
        self._cache: dict[int, tuple[float, cairo.ImageSurface]] = {}
        self._areas: list[Gtk.DrawingArea] = []

        header = Adw.HeaderBar()
        zoom_out = Gtk.Button(icon_name="zoom-out-symbolic", tooltip_text="Zoom out")
        zoom_out.connect("clicked", lambda *_: self._zoom(1 / 1.2))
        zoom_in = Gtk.Button(icon_name="zoom-in-symbolic", tooltip_text="Zoom in")
        zoom_in.connect("clicked", lambda *_: self._zoom(1.2))
        header.pack_start(zoom_out)
        header.pack_start(zoom_in)
        external = Gtk.Button(label="Open Externally")
        external.connect("clicked", self._open_externally)
        header.pack_end(external)
        self.status = Gtk.Label(label="")
        self.status.add_css_class("dim-label")
        header.pack_end(self.status)

        self.pages_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=PAGE_GAP,
            halign=Gtk.Align.CENTER, margin_top=PAGE_GAP, margin_bottom=PAGE_GAP,
        )
        scroll = Gtk.ScrolledWindow(child=self.pages_box, vexpand=True)
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(scroll)
        self.set_content(view)

        escape = Gtk.ShortcutController()
        escape.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("Escape"),
                Gtk.CallbackAction.new(lambda *_: self.close() or True),
            )
        )
        self.add_controller(escape)
        self._load()

    def _load(self) -> None:
        uri = Gio.File.new_for_path(str(self.path)).get_uri()
        try:
            self.document = Poppler.Document.new_from_file(uri, None)
        except GLib.Error as error:
            self.pages_box.append(
                Gtk.Label(label=f"Cannot open PDF: {error.message}", margin_top=40)
            )
            return
        count = min(self.document.get_n_pages(), MAX_PDF_PAGES)
        first = self.document.get_page(0)
        if first is not None:
            width, _height = first.get_size()
            if width > 0:
                self.scale = max(MIN_SCALE, min(MAX_SCALE, FIT_WIDTH / width))
        for index in range(count):
            area = Gtk.DrawingArea()
            area.set_draw_func(self._draw_page, index)
            self.pages_box.append(area)
            self._areas.append(area)
        if self.document.get_n_pages() > MAX_PDF_PAGES:
            self.pages_box.append(
                Gtk.Label(label=f"Showing the first {MAX_PDF_PAGES} pages", margin_top=8)
            )
        self.status.set_text(f"{self.document.get_n_pages()} pages")
        self._resize_areas()

    def _resize_areas(self) -> None:
        for index, area in enumerate(self._areas):
            page = self.document.get_page(index)
            if page is None:
                continue
            width, height = page.get_size()
            area.set_content_width(int(width * self.scale))
            area.set_content_height(int(height * self.scale))

    def _zoom(self, factor: float) -> None:
        self.scale = max(MIN_SCALE, min(MAX_SCALE, self.scale * factor))
        self._cache.clear()
        self._resize_areas()
        for area in self._areas:
            area.queue_draw()

    def _open_externally(self, _button) -> None:
        Gtk.FileLauncher(file=Gio.File.new_for_path(str(self.path))).launch(self, None, None)

    def _surface(self, index: int) -> cairo.ImageSurface | None:
        cached = self._cache.get(index)
        if cached is not None and cached[0] == self.scale:
            return cached[1]
        page = self.document.get_page(index)
        if page is None:
            return None
        width, height = page.get_size()
        surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, int(width * self.scale), int(height * self.scale)
        )
        context = cairo.Context(surface)
        context.scale(self.scale, self.scale)
        context.set_source_rgb(1, 1, 1)
        context.paint()
        page.render(context)
        if len(self._cache) >= SURFACE_CACHE:
            self._cache.pop(next(iter(self._cache)))
        self._cache[index] = (self.scale, surface)
        return surface

    def _draw_page(self, _area, context, _width, _height, index: int) -> None:
        surface = self._surface(index)
        if surface is not None:
            context.set_source_surface(surface, 0, 0)
            context.paint()
