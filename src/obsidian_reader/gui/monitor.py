"""Watches every vault directory and reports changes, debounced, on the main loop."""

import os
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib

DEBOUNCE_MS = 2000

_RELEVANT = {
    Gio.FileMonitorEvent.CHANGES_DONE_HINT,
    Gio.FileMonitorEvent.CREATED,
    Gio.FileMonitorEvent.DELETED,
    Gio.FileMonitorEvent.RENAMED,
    Gio.FileMonitorEvent.MOVED_IN,
    Gio.FileMonitorEvent.MOVED_OUT,
}


class VaultMonitor:
    """One Gio monitor per non-hidden vault directory, coalescing events into one callback.

    The callback fires on the GLib main loop after the vault has been quiet for
    the debounce window; the monitor set refreshes itself after each firing so
    newly created directories are watched too.
    """

    def __init__(self, root: Path, on_change):
        self.root = root
        self.on_change = on_change
        self._monitors: dict[str, Gio.FileMonitor] = {}
        self._timeout = 0
        self._cancelled = False
        self._watch_all()

    def cancel(self) -> None:
        """Stops every monitor and any pending callback."""
        self._cancelled = True
        if self._timeout:
            GLib.source_remove(self._timeout)
            self._timeout = 0
        for monitor in self._monitors.values():
            monitor.cancel()
        self._monitors.clear()

    def _watch_all(self) -> None:
        wanted = {str(self.root)}
        for dirpath, dirnames, _filenames in os.walk(self.root, followlinks=False):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            wanted.update(str(Path(dirpath) / d) for d in dirnames)
        for path in set(self._monitors) - wanted:
            self._monitors.pop(path).cancel()
        for path in wanted - set(self._monitors):
            gfile = Gio.File.new_for_path(path)
            try:
                monitor = gfile.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
            except GLib.Error:
                continue
            monitor.connect("changed", self._on_event)
            self._monitors[path] = monitor

    def _on_event(self, _monitor, gfile, _other, event) -> None:
        if event not in _RELEVANT or self._cancelled:
            return
        path = gfile.get_path() or ""
        name = os.path.basename(path)
        if name.startswith(".") or name.endswith(("~", ".tmp", ".swp")):
            return
        if self._timeout:
            GLib.source_remove(self._timeout)
        self._timeout = GLib.timeout_add(DEBOUNCE_MS, self._fire)

    def _fire(self) -> bool:
        self._timeout = 0
        if not self._cancelled:
            self._watch_all()
            self.on_change()
        return False
