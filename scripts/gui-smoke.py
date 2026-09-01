"""Drives the real window through open, render, search, and navigation on a live display."""

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import GLib

from obsidian_reader.gui.app import ReaderApplication

failures: list[str] = []
vault_path = Path(sys.argv[1]).resolve()


def check(label: str, condition: bool) -> None:
    print(f"{'ok' if condition else 'FAIL'}  {label}")
    if not condition:
        failures.append(label)


def run_checks(app):
    window = app.get_active_window()
    check("window exists", window is not None)
    check("vault opened", window.vault is not None)
    check("vault indexed notes", window.vault is not None and len(window.vault.notes) >= 2)
    check("a note is shown", bool(window.current_note))
    check("renderer produced a page", getattr(window, "_last_render", None) is not None)
    rendered = getattr(window, "_last_render", None)
    if rendered is not None:
        check("callout rendered", "callout" in rendered.body)
        check("wikilink rendered", "reader:///note/" in rendered.body)
    hits = []
    if window.vault is not None:
        from obsidian_reader.core.search import search_filenames

        hits = search_filenames(window.vault, "second")
    check("filename search finds the note", any("Second" in h.path for h in hits))
    window.reader.load_note("Second Note.md")

    def after_navigation():
        check("navigation updated current note", window.current_note == "Second Note.md")

        window._set_zen(True)
        check("zen hides sidebar and chrome", not window.split.get_show_sidebar())
        check("zen reveals no top bars", not window.toolbar_view.get_reveal_top_bars())
        window._set_zen(False)
        check("leaving zen restores the sidebar", window.split.get_show_sidebar())
        check("leaving zen restores the header", window.toolbar_view.get_reveal_top_bars())

        import tempfile

        from gi.repository import Gio

        pdf_path = Path(tempfile.mkdtemp()) / "export.pdf"
        window._export_pdf_to(Gio.File.new_for_path(str(pdf_path)))

        def check_pdf():
            written = pdf_path.exists() and pdf_path.read_bytes()[:5] == b"%PDF-"
            check("PDF export wrote a real PDF", written)
            toggle = window.lookup_action("toggle-source")
            window._on_toggle_source(toggle, GLib.Variant.new_boolean(True))
            GLib.timeout_add(1200, lambda: (app.quit(), False)[1])
            return False

        GLib.timeout_add(2500, check_pdf)
        return False

    GLib.timeout_add(1500, after_navigation)
    return False


def main() -> int:
    app = ReaderApplication()

    def kick_off(application):
        window = application.get_active_window()
        window.open_path(vault_path)
        GLib.timeout_add(3500, run_checks, application)

    app.connect_after("activate", kick_off)
    app.run([sys.argv[0]])
    print("RESULT:", "FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
