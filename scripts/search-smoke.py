"""Drives the real window through a search that has to clear: the box emptied, and a vault switched.

Two invented vaults are made in a temporary folder. A search opens a long note with
its words marked; emptying the box must take every mark out and leave the note where
it was read to; Escape must empty the box; opening another vault must leave nothing
of the first vault's search, and no result, error page included, may carry marks it
should not. Run on a live display, by `make smoke`.
"""

import sys
import tempfile
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import GLib  # noqa: E402

from solander.core.pagescripts import SCRIPT_WORLD  # noqa: E402
from solander.gui.app import ReaderApplication  # noqa: E402

WATCHDOG_SECONDS = 180
MARKS = "String(document.querySelectorAll('mark.search-hit').length)"
POSITION = "String(Math.round(window.scrollY))"

failures: list[str] = []


def check(label: str, condition: bool) -> None:
    print(f"{'ok' if condition else 'FAIL'}  {label}", flush=True)
    if not condition:
        failures.append(label)


def make_vaults(root: Path) -> tuple[Path, Path]:
    first, second = root / "Harbour", root / "River"
    first.mkdir()
    second.mkdir()
    lines = "\n\n".join(
        f"Paragraph {i} about the harbour lantern and its keeper." for i in range(120)
    )
    (first / "Lantern Notes.md").write_text(f"# Lantern Notes\n\n{lines}\n")
    (first / "Lantern Index.md").write_text("# Lantern Index\n\nSee [[Lantern Notes]].\n")
    (second / "Otter.md").write_text("# Otter\n\nRiver notes only.\n")
    (second / "Heron.md").write_text("# Heron\n\nBirds.\n")
    return first, second


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        first, second = make_vaults(Path(tmp))
        app = ReaderApplication()
        target: list[Path] = [first]

        def later(ms, step, *args):
            GLib.timeout_add(ms, lambda: (step(*args), False)[1])

        def ask(window, script, then):
            def answered(view, result, _data):
                try:
                    then(view.evaluate_javascript_finish(result).to_string())
                except GLib.Error as error:
                    then(f"error: {error.message}")

            window.reader.webview.evaluate_javascript(
                script, -1, SCRIPT_WORLD, None, None, answered, None
            )

        def rows(window) -> list[str]:
            found, row = [], window.search_results.get_first_child()
            while row is not None:
                found.append(getattr(row, "note_path", ""))
                row = row.get_next_sibling()
            return found

        def when_ready(window, step, tries=0):
            ready = (
                window.vault is not None
                and window.vault.root == target[0]
                and window.search_index is not None
                and window.search_index.ready
            )
            if ready or tries > 200:
                step(window)
            else:
                later(300, when_ready, window, step, tries + 1)

        def search(window):
            window._show_search()
            window.search_entry.set_text("lantern keeper")
            later(
                400,
                lambda: (
                    window._on_search_submitted(window.search_entry),
                    later(600, open_note, window),
                ),
            )

        def open_note(window):
            row = window.search_results.get_first_child()
            while row is not None and getattr(row, "note_path", "") != "Lantern Notes.md":
                row = row.get_next_sibling()
            check("full-text search finds the long note", row is not None)
            if row is None:
                return finish()
            window._on_search_row(None, row)
            later(2500, ask, window, MARKS, lambda n: marked(window, n))

        def marked(window, count):
            check(
                f"the note opened from the search carries its marks ({count})",
                count.isdigit() and int(count) > 0,
            )
            ask(
                window,
                "window.scrollTo(0, 1500); ''",
                lambda _: later(500, ask, window, POSITION, lambda at: clear(window, at)),
            )

        def clear(window, before):
            window.search_entry.set_text("")
            later(
                2500,
                ask,
                window,
                MARKS,
                lambda n: ask(window, POSITION, lambda at: cleared(window, n, before, at)),
            )

        def cleared(window, count, before, after):
            check(f"emptying the box takes every mark out of the note ({count})", count == "0")
            close = before.isdigit() and after.isdigit() and abs(int(before) - int(after)) < 60
            check(f"and the note stays where it was read to ({before} -> {after})", close)
            window.search_entry.set_text("lantern")
            window.search_entry.emit("stop-search")
            later(400, escaped, window)

        def escaped(window):
            check("Escape empties the search box", window.search_entry.get_text() == "")
            window.search_entry.set_text("lantern")
            window._on_search_submitted(window.search_entry)
            later(600, switch, window)

        def switch(window):
            check("the first vault shows results before the switch", bool(rows(window)))
            target[0] = second
            window._open_vault(second)
            later(800, when_ready, window, lambda w: later(600, switched, w))

        def switched(window):
            shown = rows(window)
            check(
                "opening another vault empties the search box", window.search_entry.get_text() == ""
            )
            check(
                f"and no result names a note the new vault lacks ({shown})",
                all(not path or window.vault.has_file(path) for path in shown),
            )

            class Leftover:
                note_path = "Lantern Notes.md"

            before = window.current_note
            window._on_search_row(None, Leftover())
            later(1500, stale, window, before)

        def stale(window, before):
            check(
                f"an old vault's result opens nothing ({before} -> {window.current_note})",
                window.current_note == before,
            )
            window._pending_highlight = ["missing"]
            window.reader.load_note("Missing Note.md")
            later(2000, ask, window, MARKS, lambda n: error_page(window, n))

        def error_page(window, count):
            check(
                f"an error page carries no search marks, though it names the word ({count})",
                count == "0",
            )
            finish()

        def finish():
            app.quit()

        def kick_off(application):
            window = application.get_active_window()
            window.set_default_size(1400, 900)
            window._open_vault(first)
            later(800, when_ready, window, search)

        GLib.timeout_add_seconds(
            WATCHDOG_SECONDS, lambda: (check("finished in time", False), app.quit(), False)[2]
        )
        app.connect_after("activate", kick_off)
        app.run([sys.argv[0]])
    print("RESULT:", "FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
