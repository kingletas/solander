"""Drives the real window through open, render, search, and navigation on a live display."""

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Gio, GLib

from obsidian_reader.gui.app import ReaderApplication

failures: list[str] = []
checks_run: list[str] = []
vault_path = Path(sys.argv[1]).resolve()


def check(label: str, condition: bool) -> None:
    print(f"{'ok' if condition else 'FAIL'}  {label}")
    checks_run.append(label)
    if not condition:
        failures.append(label)


def run_checks(app):
    window = app.get_active_window()
    check("window exists", window is not None)
    check("vault opened", window.vault is not None)
    check("vault indexed notes", window.vault is not None and len(window.vault.notes) >= 2)
    check("a note is shown", bool(window.current_note))
    rendered = window.reader.last_render
    check("renderer produced a page", rendered is not None)
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
        check("zen hides sidebar and chrome", not window.sidebar_widget.get_visible())
        check("zen reveals no top bars", not window.toolbar_view.get_reveal_top_bars())
        window._set_zen(False)
        check("leaving zen restores the sidebar", window.sidebar_widget.get_visible())
        check("leaving zen restores the header", window.toolbar_view.get_reveal_top_bars())

        check("sidebar is resizable", window.paned.get_position() > 0)
        window.paned.set_position(340)
        check("sidebar width follows the drag position", window.paned.get_position() == 340)

        window.open_in_new_tab("A.md")

        def check_tabs():
            check("a second tab opened", window.tab_view.get_n_pages() == 2)
            check("new tab shows its note", window.current_note == "A.md")
            window._close_current_tab()
            check("closing returns to one tab", window.tab_view.get_n_pages() == 1)
            check_panels()
            return False

        GLib.timeout_add(1200, check_tabs)
        return False

    def check_panels():
        graph = window.graph
        check("link graph built", graph is not None and graph.ready)
        if graph is not None:
            mentions = graph.backlinks.get("Second Note.md", [])
            linked = any(m.source == "A.md" for m in mentions)
            check("backlink recorded for the linked note", linked)
            check("tag indexed from the note body", "alpha" in graph.tags)
            hits = window.search_index.search_content("tag:alpha", graph.note_tags)
            check("tag: search operator finds the note", [h.path for h in hits] == ["A.md"])
        window._update_links_panel()
        check("links panel has rows", window.links_list.get_first_child() is not None)
        window._refresh_tags_panel()
        check("tags panel has rows", window.tags_list.get_first_child() is not None)
        row = window.bookmarks_list.get_first_child()
        bookmarked = row is not None and getattr(row, "note_path", "") == "A.md"
        check("bookmarks panel lists the bookmark", bookmarked)
        window._preview_pending = "A.md"
        window._show_preview()

        def check_preview():
            shown = window._preview_reader is not None and window.preview_popover.get_visible()
            check("hover preview popover shows", shown)
            window._cancel_preview()
            hidden = window._preview_reader is None or not window.preview_popover.get_visible()
            check("hover preview hides on cancel", hidden)
            start_live()
            return False

        GLib.timeout_add(900, check_preview)

    def start_live():
        (vault_path / "Live.md").write_text("Watched: [[Second Note]] and a #livetag here.\n")

        def check_live():
            graph = window.graph
            mentions = graph.backlinks.get("Second Note.md", []) if graph else []
            check("monitor picked up the new note", any(m.source == "Live.md" for m in mentions))
            check("new tag is live in the graph", graph is not None and "livetag" in graph.tags)
            hits = window.search_index.search_content("watched")
            check("new note is searchable without a reload", any(h.path == "Live.md" for h in hits))
            check_retrieval()
            return False

        GLib.timeout_add(5200, check_live)

    def check_retrieval():
        from obsidian_reader.core.search import search_filenames

        fuzzy_hits = search_filenames(window.vault, "scnt")
        check("fuzzy quick-open matches a subsequence", fuzzy_hits[0].path == "Second Note.md")
        check("recent notes are tracked", "Second Note.md" in window.store.state.recent_notes)
        window._update_local_graph()
        check("local graph pane has neighbors", len(window.local_graph.neighbors) >= 1)
        window._pending_highlight = "note"
        window.reader.load_note("A.md")

        def check_highlight():
            controller = window.reader.webview.get_find_controller()
            check("search hit highlighting ran", controller.get_search_text() == "note")
            check("highlight consumed after one load", window._pending_highlight == "")
            continue_pdf()
            return False

        GLib.timeout_add(1500, check_highlight)

    def continue_pdf():
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

    GLib.timeout_add(1500, after_navigation)
    return False


def main() -> int:
    app = ReaderApplication()
    # Without this, a reader already running for the real vault owns the app id,
    # activate is forwarded to it, and zero checks would read as a pass.
    app.set_flags(app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)

    def kick_off(application):
        window = application.get_active_window()
        window.open_path(vault_path)
        GLib.timeout_add(3500, run_checks, application)

    app.connect_after("activate", kick_off)
    app.run([sys.argv[0]])
    if not checks_run:
        print("RESULT: FAIL (no checks ran)")
        return 1
    print("RESULT:", "FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
