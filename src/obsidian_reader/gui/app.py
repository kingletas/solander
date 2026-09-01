"""The application object: single instance, path handoff, session restore."""

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

from .. import APP_ID
from .window import ReaderWindow


class ReaderApplication(Adw.Application):
    """One process per user; a second launch hands its path to the running instance."""

    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)

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
