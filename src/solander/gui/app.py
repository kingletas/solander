"""The application object: single instance, path handoff, session restore."""

import gc
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from .. import APP_ID, APP_NAME
from .window import ReaderWindow

GC_INTERVAL_SECONDS = 10


class ReaderApplication(Adw.Application):
    """One process per user; a second launch hands its path to the running instance."""

    def __init__(self):
        # Wayland takes a toplevel's app id from the program name, and the desktop
        # matches a window to its .desktop file — and therefore to its icon — by
        # exactly that. Launched as `python -m solander.cli` the program name is
        # "cli.py", which matches nothing, so the window draws a placeholder icon.
        GLib.set_prgname(APP_ID)
        GLib.set_application_name(APP_NAME)
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        Gtk.Window.set_default_icon_name(APP_ID)
        # Cyclic garbage can hold GTK and WebKit objects (a closed tab's web
        # view), and WebKit aborts when finalized off the main thread — which is
        # exactly where the collector lands once the index sync thread exists.
        # So automatic collection is off, and the main loop collects instead.
        gc.disable()
        GLib.timeout_add_seconds(GC_INTERVAL_SECONDS, self._collect)

    @staticmethod
    def _collect() -> bool:
        gc.collect()
        return True

    def _window(self) -> ReaderWindow:
        window = self.get_active_window()
        if window is None:
            window = ReaderWindow(self)
        return window

    def do_activate(self) -> None:
        window = self._window()
        window.present()
        if window.vault is None and not window.current_note:
            window.restore_or_welcome()

    def do_open(self, files, _count, _hint) -> None:
        window = self._window()
        window.present()
        for gfile in files:
            path = gfile.get_path()
            if path:
                window.open_path(Path(path))
