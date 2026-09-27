"""Drives the real window through open, render, search, and navigation on a live display."""

import re
import sys
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Gio, GLib

from solander.gui.app import ReaderApplication

failures: list[str] = []
checks_run: list[str] = []
finished: list[bool] = []
vault_path = Path(sys.argv[1]).resolve()

# The whole run is one chain of GLib callbacks, so an exception in any of them
# takes every check after it with it. Long enough that a slow machine finishes.
WATCHDOG_SECONDS = 300

# How long the run waits for the vault's landing note before checking anything.
# The floor is the delay this used to wait unconditionally, so waiting on the
# condition can only ever extend the wait and never start the checks earlier.
FIRST_NOTE_POLL_MS = 250
FIRST_NOTE_FLOOR_TRIES = 14
FIRST_NOTE_TRIES = 60


def check(label: str, condition: bool) -> None:
    print(f"{'ok' if condition else 'FAIL'}  {label}")
    checks_run.append(label)
    if not condition:
        failures.append(label)


def record_crash(kind, value, trace) -> None:
    """Turns an exception in a GLib callback into a failure instead of a silence.

    GLib prints an unhandled callback exception and carries on, so the chain of
    timeouts that drives this run simply stops, and every check after the crash
    reads the same as a check that was never written. A run that ended early used
    to print PASS.
    """
    import traceback

    traceback.print_exception(kind, value, trace)
    check(f"a callback raised {kind.__name__}: {value}", False)


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
        from solander.core.search import search_filenames

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

        badge = window.readonly_badge.get_child()
        check("the read-only control carries its word", badge.get_label() == "Read-only")
        check("the read-only word is on screen", badge.get_mapped() and badge.get_width() > 40)

        window.reader.emit("open-external-uri", "mailto:ana@example.org?subject=Hi")
        dialog = window.get_visible_dialog()
        check("a mail link asks before opening", dialog is not None)
        if dialog is not None:
            said = dialog.get_body()
            check("the question names the address", "ana@example.org" in said)
            check("the question names what the link fills in", "the subject" in said)
            # libadwaita 1.5 ignores a close made in the same turn as the present.
            GLib.timeout_add(100, lambda: dialog.force_close() or False)

        check("sidebar is resizable", window.paned.get_position() > 0)
        window.paned.set_position(340)
        check("sidebar width follows the drag position", window.paned.get_position() == 340)

        window.open_in_new_tab("A.md")

        def check_tabs():
            # A dialog closes at the end of its animation, so this is asked a beat later.
            check("cancelling leaves no question open", window.get_visible_dialog() is None)
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

    def tree_rows():
        model = window.tree.selection.get_model()
        return [model.get_item(i) for i in range(model.get_n_items())]

    def start_live():
        # An expanded folder, so the check below can see whether a vault change collapses it.
        (vault_path / "Folder").mkdir()
        (vault_path / "Folder" / "Inside.md").write_text("# Inside\n")
        window.tree.refresh()
        folder = next((row for row in tree_rows() if row.get_item().rel == "Folder"), None)
        check("the tree lists a new folder", folder is not None)
        if folder is not None:
            folder.set_expanded(True)
        check("the folder expands", folder is not None and folder.get_expanded())
        (vault_path / "Live.md").write_text("Watched: [[Second Note]] and a #livetag here.\n")

        def check_live():
            rows = {row.get_item().rel: row for row in tree_rows()}
            check("the tree shows the new note", "Live.md" in rows)
            check(
                "a vault change leaves an expanded folder expanded",
                "Folder" in rows and rows["Folder"].get_expanded(),
            )
            check("the expanded folder still lists its note", "Folder/Inside.md" in rows)
            sort = window.lookup_action("tree-sort")
            sort.activate(GLib.Variant.new_string("modified"))
            items = [row.get_item() for row in tree_rows()]
            top_files = [item.rel for item in items if not item.is_dir and "/" not in item.rel]
            newest = top_files[:1] == ["Live.md"]
            check("newest first puts the note just written at the top", newest)
            resorted = {row.get_item().rel: row for row in tree_rows()}
            check(
                "changing the sort leaves an expanded folder expanded",
                "Folder" in resorted and resorted["Folder"].get_expanded(),
            )
            sort.activate(GLib.Variant.new_string("name"))
            items = [row.get_item() for row in tree_rows()]
            top_files = [item.rel for item in items if not item.is_dir and "/" not in item.rel]
            check("name order is back", top_files == sorted(top_files, key=str.casefold))
            graph = window.graph
            mentions = graph.backlinks.get("Second Note.md", []) if graph else []
            check("monitor picked up the new note", any(m.source == "Live.md" for m in mentions))
            check("new tag is live in the graph", graph is not None and "livetag" in graph.tags)
            hits = window.search_index.search_content("watched")
            check("new note is searchable without a reload", any(h.path == "Live.md" for h in hits))
            page = window._provide_page("/note/Query.md", window.reader.webview)
            check("dataview table renders", '<div class="dataview"><table>' in page)
            check("dataview inline expression evaluates", ">8</span>" in page)
            board = window._provide_page("/note/Sprint.md", window.reader.webview)
            lanes = board.count('<div class="kanban-column">')
            check("kanban note renders as a board", lanes == 2)
            check("kanban cards keep their wikilinks", "reader:///note/A.md" in board)
            base_page = window._provide_page("/note/Things.base", window.reader.webview)
            check("base file renders its table view", "<table>" in base_page)
            check("base filter matched the fixture note", "Query" in base_page)
            drawing = window._provide_page("/note/Draw.excalidraw.md", window.reader.webview)
            check("excalidraw note renders as SVG", "<svg" in drawing and "<rect" in drawing)
            # The page carries its own `url()` for the bundled faces, so what
            # must be absent is the snippet's, not every one on the page.
            check(
                "vault css snippet is applied sanitized",
                "teal" in page and "http://x/y.png" not in page,
            )
            inside = window._provide_page("/note/Sub/Inside.md", window.reader.webview)
            check(
                "the page no longer repeats the path the header bar carries",
                "reader:///action/reveal-folder?arg=Sub" not in inside,
            )
            window.title_widget.show_note("Sub/Inside.md")
            check(
                "the header bar carries the folders the note sits in",
                window.title_widget.steps() == ["Sub"],
            )
            one_title = (
                '<h1 class="inline-title">Inside</h1>' in inside
                and inside.count(">Inside</h1>") == 1
            )
            check("a duplicate body H1 yields to the header title", one_title)
            second = window._provide_page("/note/Second Note.md", window.reader.webview)
            check(
                "a note is titled by the heading it opens with",
                '<h1 class="inline-title">B</h1>' in second,
            )
            bare = window._provide_page("/note/Bare Note.md", window.reader.webview)
            check(
                "a note with no leading heading keeps its filename",
                '<h1 class="inline-title">Bare Note</h1>' in bare,
            )
            check("metadata line reports the update date", "Updated " in second)
            mentions_shown = 'class="backlinks"' in second and "reader:///note/A.md" in second
            check("linked mentions follow the content", mentions_shown)
            structured = window.renderer.render("Long.md")
            window._fill_outline(structured.outline)
            rows = 0
            row = window.outline_list.get_first_child()
            while row is not None:
                rows += 1 if getattr(row, "anchor", "") else 0
                row = row.get_next_sibling()
            check("outline panel lists the note's headings", rows == 3)
            window._set_outline_visible(True)
            opened = window.outline_split.get_show_sidebar() and window.outline_toggle.get_active()
            check("outline opens as a native panel", opened)
            window._set_outline_visible(False)
            closed = (
                not window.outline_split.get_show_sidebar()
                and not window.outline_toggle.get_active()
            )
            check("outline hides from its own controls", closed)
            panel = window.outline_split.get_sidebar()
            dressed = "outline-panel" in panel.get_css_classes()
            check("outline panel wears the canvas dress", dressed)
            no_rail_page = window.sidebar_stack.get_child_by_name("outline") is None
            check("the rail carries no outline page", no_rail_page)
            crumb_action = window.lookup_action("show-breadcrumb")
            crumb_action.change_state(GLib.Variant.new_boolean(False))
            plain = window._provide_page("/note/Second Note.md", window.reader.webview)
            untitled = '<h1 class="inline-title">' not in plain
            check("title and breadcrumb can be hidden too", untitled)
            crumb_action.change_state(GLib.Variant.new_boolean(True))
            welcome = window._provide_page("/page/welcome", window.reader.webview)
            hero = 'class="welcome-name"' in welcome and 'class="action-card"' in welcome
            check("welcome page carries the frontispiece", hero)
            check("welcome hero inlines the app mark", "<svg" in welcome)
            # The fixture vault is not under the home directory, so a recent vault
            # that is stands in for one; the card is drawn whether or not it exists.
            recents = window.store.state.recent_vaults
            home = str(Path.home())
            homed = str(Path.home() / "Smoke Card Vault")
            recents.insert(0, homed)
            try:
                carded = window._provide_page("/page/welcome", window.reader.webview)
            finally:
                recents.remove(homed)
            check("a welcome vault card names its vault", "Smoke Card Vault" in carded)
            check(
                "the welcome page does not print the home directory",
                home not in carded and "~/Smoke Card Vault" not in carded,
            )
            flow = window._provide_page("/note/Flow.md", window.reader.webview)
            drew = 'class="mermaid-diagram"' in flow and "start" in flow and "ok?" in flow
            check("mermaid flowchart renders as static SVG", drew)
            check("author stroke styling reaches the diagram", 'style="stroke:#080"' in flow)
            labeled = "gantt diagrams are not supported" in flow
            check("unsupported mermaid kinds name themselves", labeled)
            from solander import APP_ID

            # Wayland names a toplevel by the program name, and the desktop matches
            # a window to its .desktop file, and so to its icon, by exactly that.
            check("the process identifies itself as the app id",
                  GLib.get_prgname() == APP_ID)
            railed = "reader-rail" in window.sidebar_widget.get_css_classes()
            check("the sidebar is the rail surface", railed)
            theme_action = window.lookup_action("theme")
            mode_action = window.lookup_action("appearance")
            theme_action.change_state(GLib.Variant.new_string("blood-record"))
            bloodied = window._provide_page("/note/A.md", window.reader.webview)
            check("theme switch re-renders the page in the new theme",
                  "theme-blood-record" in bloodied)
            check("a dark-only theme greys out the light/dark choice",
                  not mode_action.get_enabled())
            theme_action.change_state(GLib.Variant.new_string("corrosion"))
            other = window._provide_page("/note/A.md", window.reader.webview)
            check("a second family theme shares the rules and swaps the palette",
                  "theme-archive" in other and "theme-corrosion" in other
                  and "theme-blood-record" not in other)
            theme_action.change_state(GLib.Variant.new_string("stone"))
            restored = window._provide_page("/note/A.md", window.reader.webview)
            check("switching back restores the original theme",
                  "theme-blood-record" not in restored)
            check("the light/dark choice comes back with it", mode_action.get_enabled())
            crowned = window.rail_title.get_label() == window.vault.root.name.upper()
            check("the vault name crowns the rail", crowned)
            guide = window._provide_page("/page/user-guide", window.reader.webview)
            check("user guide renders in-app", "The window" in guide and "<table>" in guide)
            check("guide cross-links stay in-app", "reader:///page/getting-started" in guide)
            started = window._provide_page("/page/getting-started", window.reader.webview)
            check("getting started renders in-app", "Open your vault" in started)
            mindmap = window._provide_page("/mindmap/A.md", window.reader.webview)
            check("mind map renders the note structure", "<svg" in mindmap and ">A<" in mindmap)
            back = "reader:///note/A.md" in mindmap and "Back to A" in mindmap
            check("mind map offers the way back", back)
            from solander.core.search import search_filenames

            names = [node.rel for node in window.tree._list_directory("")]
            check("tree lists the soon-hidden folder", "Sub" in names)
            key = str(window.vault.root)
            window.store.state.hidden_folders[key] = ["Sub"]
            window._apply_hidden_folders()
            names = [node.rel for node in window.tree._list_directory("")]
            hits = window._quick_hits(search_filenames(window.vault, "inside"))
            check("hidden folder leaves the tree", "Sub" not in names)
            check("hidden folder leaves quick-open", all("Sub/" not in h.path for h in hits))
            check(
                "a folder hidden here leaves full-text search too",
                all("Sub/" not in h.path for h in window._ranked_hits(hits)),
            )
            window._unhide_all_folders()
            names = [node.rel for node in window.tree._list_directory("")]
            check("unhide restores the folder", "Sub" in names)
            from gi.repository import Gtk

            window._on_page_action(None, "reveal-folder", "Sub")
            position = window.tree.selection.get_selected()
            selected = None
            if position != Gtk.INVALID_LIST_POSITION:
                row = window.tree.selection.get_model().get_item(position)
                selected = row.get_item() if row is not None else None
            revealed = selected is not None and selected.rel == "Sub"
            check("breadcrumb reveal selects the folder in the tree", revealed)
            window._on_page_action(None, "tag", "alpha")
            searched = window.search_entry.get_text() == "tag:alpha"
            check("tag chip action runs a tag search", searched)
            check_retrieval()
            return False

        GLib.timeout_add(5200, check_live)

    def check_retrieval():
        from solander.core.search import search_filenames

        fuzzy_hits = search_filenames(window.vault, "scnt")
        check("fuzzy quick-open matches a subsequence", fuzzy_hits[0].path == "Second Note.md")
        check("recent notes are tracked", "Second Note.md" in window.store.state.recent_notes)
        window._update_local_graph()
        check("local graph pane has neighbors", len(window.local_graph.neighbors) >= 1)
        from gi.repository import Gdk

        graph_view = window.local_graph
        moved = graph_view.on_key(Gdk.KEY_Right) and graph_view.selected == 0
        check("the arrow keys select a note in the local graph", moved)
        first = graph_view.neighbors[0][0] if graph_view.neighbors else ""
        opened = []
        real_open = graph_view.on_activate
        graph_view.on_activate = opened.append
        graph_view.on_key(Gdk.KEY_Return)
        graph_view.on_activate = real_open
        check("Enter opens the selected note from the local graph", opened == [first])
        window._pending_highlight = ["alpha", "callout"]
        window.reader.load_note("A.md", anchor="search-hit")

        def check_highlight():
            check("highlight consumed after one load", window._pending_highlight == [])
            script = (
                "[document.querySelectorAll('mark.search-hit').length,"
                " document.querySelectorAll('#search-hit').length].join(',')"
            )

            def counted(webview, result) -> None:
                marks, first = webview.evaluate_javascript_finish(result).to_string().split(",")
                every = int(marks) >= 2
                check("every search word is marked in the note, not the first alone", every)
                check("the first hit carries the anchor the note opens at", first == "1")
                check_block_link()

            # A world of its own, because the page's policy forbids scripts in the document.
            webview = window.reader.webview
            webview.evaluate_javascript(script, -1, "smoke", None, None, counted)
            return False

        def check_block_link():
            """Follows a `[[Note#^id]]` link the way a click does, and finds the block on screen."""
            page = window._provide_page("/note/Linker.md", window.reader.webview)
            match = re.search(r'href="(reader:///note/Blocks\.md#[^"]*)"', page)
            href = match.group(1) if match else ""
            check("a block link keeps the block in its address", href.endswith("#block-deep"))
            window.reader.webview.load_uri(href or "reader:///note/Blocks.md")

            def measure_block():
                script = (
                    "(() => { const b = document.getElementById('block-deep');"
                    " if (!b) return 'none';"
                    " const top = b.getBoundingClientRect().top;"
                    " const seen = top >= 0 && top < window.innerHeight;"
                    " return [window.scrollY > 0, seen].join(','); })()"
                )

                def placed(webview, result) -> None:
                    answer = webview.evaluate_javascript_finish(result).to_string()
                    check("the linked block is on the page", answer != "none")
                    scrolled = answer == "true,true"
                    check("the note opens scrolled to the block, not at the top", scrolled)
                    window._read_scroll_positions(check_scroll_read)

                webview = window.reader.webview
                webview.evaluate_javascript(script, -1, "smoke", None, None, placed)
                return False

            def check_scroll_read(positions) -> None:
                where = positions.get("Blocks.md", 0.0)
                print(f"   Blocks.md read at {where:.3f} of the way down")
                check("closing would remember how far down a note was read", where > 0.5)
                window._pending_scroll = {"Blocks.md": 0.5}
                window.reader.load_note("A.md")
                GLib.timeout_add(1000, reopen_blocks)

            def reopen_blocks():
                window.reader.load_note("Blocks.md")
                GLib.timeout_add(1500, measure_restore)
                return False

            def measure_restore():
                script = (
                    "(() => { const room = document.documentElement.scrollHeight"
                    " - window.innerHeight; return String(window.scrollY / room); })()"
                )

                def restored(webview, result) -> None:
                    where = float(webview.evaluate_javascript_finish(result).to_string())
                    print(f"   Blocks.md restored to {where:.3f} of the way down")
                    check("a restored note opens where it was read to", abs(where - 0.5) < 0.05)
                    check("a restored position is used once", window._pending_scroll == {})
                    check_open_time()

                webview = window.reader.webview
                webview.evaluate_javascript(script, -1, "smoke", None, None, restored)
                return False

            def check_open_time():
                """Times a note of ordinary size from asking for it to WebKit finishing the page."""
                from gi.repository import WebKit

                paragraph = "A paragraph with **bold**, a [[A]] link, a #tag and `code`. " * 4
                table = "| a | b |\n|---|---|\n" + "| 1 | [[Second Note]] |\n" * 10
                (vault_path / "Typical.md").write_text(
                    "# Typical\n\n" + ("## Part\n\n" + (paragraph + "\n\n") * 4 + table
                                        + "\n```python\nprint(1)\n```\n\n") * 6
                )
                webview = window.reader.webview
                started = {}

                def finished(view, event) -> None:
                    ours = "Typical.md" in (view.get_uri() or "")
                    if event != WebKit.LoadEvent.FINISHED or not ours:
                        return
                    view.disconnect(handler)
                    took = time.monotonic() - started["at"]
                    size = (vault_path / "Typical.md").stat().st_size // 1024
                    print(f"   a {size} KB note opened in {took * 1000:.0f} ms")
                    check("an ordinary note opens in under a second", took < 1.0)
                    GLib.timeout_add(300, lambda: (check_responsive(), False)[1])

                handler = webview.connect("load-changed", finished)
                started["at"] = time.monotonic()
                window.reader.load_note("Typical.md")

            def check_responsive():
                """Opens a 1 MB note and times the window's own loop while it renders.

                The note is written here rather than with the other fixtures, so the
                first index pass is not slowed by it, and it is removed afterwards.
                """
                section = (
                    "## Section\n\n"
                    + ("Words with **bold**, a [[A]] link, a #tag and `code`. " * 6 + "\n\n") * 5
                    + "| a | b |\n|---|---|\n" + "| 1 | [[Second Note]] |\n" * 40 + "\n"
                    + "```python\n" + "def f(x):\n    return x * 2\n" * 30 + "```\n\n"
                )
                huge = vault_path / "Huge.md"
                huge.write_text(section * (1024 * 1024 // len(section) + 1))
                window.reader.last_render = None
                started = time.monotonic()
                ticks = {"last": started, "gap": 0.0}

                def tick() -> bool:
                    now = time.monotonic()
                    ticks["gap"] = max(ticks["gap"], now - ticks["last"])
                    ticks["last"] = now
                    rendered = window.reader.last_render
                    if now - started > 1.0 and "notice" not in ticks:
                        ticks["notice"] = window.foot.measure.get_label()
                    if rendered is None and now - started < 60:
                        return True
                    took = now - started
                    worst = ticks["gap"] * 1000
                    print(f"   Huge.md rendered in {took:.1f} s; longest stall {worst:.0f} ms")
                    check("a 1 MB note renders", rendered is not None)
                    check("the window keeps answering while it renders", worst < 250)
                    notice = ticks.get("notice", "")
                    check("the foot says a long note is still opening", notice == "Opening Huge…")
                    GLib.timeout_add(
                        600,
                        lambda: check(
                            "the notice goes once the page is in",
                            "Opening" not in window.foot.measure.get_label()
                            and not window.foot.working.get_spinning(),
                        ),
                    )
                    huge.unlink(missing_ok=True)
                    window.reader.load_note("A.md")
                    GLib.timeout_add(1000, back_to_a)
                    return False

                window.reader.load_note("Huge.md")
                GLib.timeout_add(20, tick)

            def back_to_a():
                check_text_scale()
                return False

            def check_tab_chain(tries: int = 0):
                """Walks Tab's focus chain from the page, the way the key does, until it closes.

                Tab is bound to the window's move-focus signal, so emitting it is the
                key's own path. A window that is not active cannot hold focus, and
                every step then re-grabs the same row, so the walk needs one.
                """
                from gi.repository import Gtk, WebKit

                if not window.is_active() and tries < 15:
                    window.present()
                    GLib.timeout_add(200, check_tab_chain, tries + 1)
                    return False
                if not window.is_active():
                    print("SKIP  Tab order: the window is not the active one, so focus cannot move")
                    window._show_mindmap()
                    GLib.timeout_add(1000, check_map_toggle_on)
                    return False
                window.sidebar_widget.set_visible(True)
                window.sidebar_stack.set_visible_child_name("files")
                window.reader.webview.grab_focus()
                stops = []
                for _ in range(80):
                    window.emit("move-focus", Gtk.DirectionType.TAB_FORWARD)
                    focus = window.get_focus()
                    if stops and focus is stops[0]:
                        break
                    stops.append(focus)
                closed = bool(stops) and window.get_focus() is stops[0]
                in_tree = [w for w in stops if w.get_ancestor(Gtk.ListView) is window.tree.view]
                tabs = [w for w in stops if (w.get_tooltip_text() or "") in PANEL_NAMES]
                page = [
                    w for w in stops
                    if isinstance(w, WebKit.WebView) or w.get_ancestor(WebKit.WebView)
                ]
                print(f"   Tab visits {len(stops)} stops: {len(tabs)} panel tabs, "
                      f"{len(in_tree)} in the file tree, {len(page)} in the page")
                check("Tab comes back round to where it started", closed)
                check("Tab reaches every sidebar panel", len(tabs) == len(PANEL_NAMES))
                check("Tab reaches the page", len(page) >= 1)
                check("the file tree is one Tab stop, not one per row", len(in_tree) == 1)
                window._show_mindmap()
                GLib.timeout_add(1000, check_map_toggle_on)
                return False

            def check_text_scale():
                """Raises the desktop's text scaling by half and reads the page's type size."""
                from gi.repository import Gtk

                settings = Gtk.Settings.get_default()
                standard = settings.get_property("gtk-xft-dpi")
                script = "getComputedStyle(document.documentElement).fontSize"

                def read(then):
                    def answered(webview, result) -> None:
                        then(webview.evaluate_javascript_finish(result).to_string())

                    webview = window.reader.webview
                    webview.evaluate_javascript(script, -1, "smoke", None, None, answered)
                    return False

                def at_standard(before: str) -> None:
                    settings.set_property("gtk-xft-dpi", int(standard * 1.5))
                    GLib.timeout_add(800, read, at_large)

                def at_large(after: str) -> None:
                    print(f"   page type {before_size[0]} at the standard DPI, {after} at 1.5x")
                    check("the page follows the desktop's text scaling", after == "24px")
                    settings.set_property("gtk-xft-dpi", standard)
                    GLib.timeout_add(500, check_tab_chain)

                before_size = []

                def remember(before: str) -> None:
                    before_size.append(before)
                    at_standard(before)

                read(remember)

            GLib.timeout_add(1500, measure_block)

        def check_map_toggle_on():
            uri = window.reader.webview.get_uri() or ""
            check("Ctrl+M switches to the mind map", uri.startswith("reader:///mindmap/"))
            check("the map still counts as the note", window.current_note == "A.md")
            window._show_mindmap()
            GLib.timeout_add(1000, check_map_toggle_off)
            return False

        def check_map_toggle_off():
            uri = window.reader.webview.get_uri() or ""
            check("Ctrl+M toggles back to the note", uri.startswith("reader:///note/A.md"))
            window._refresh_quick_list()
            has_rows = window.quick_list.get_first_child() is not None
            check("recent notes populate the sidebar quick list", has_rows)
            key = str(window.vault.root)
            window._toggle_pin()
            check("pin adds the note", "A.md" in window.store.state.pinned_notes.get(key, []))
            first = window.quick_list.get_first_child()
            leads = first is not None and getattr(first, "note_path", "") == "A.md"
            check("pinned note leads the quick list", leads)
            window._toggle_pin()
            unpinned = "A.md" not in window.store.state.pinned_notes.get(key, [])
            check("unpin removes it again", unpinned)
            window.quick_expander.set_expanded(False)
            check("pinned & recent collapses", window.store.state.quick_expanded is False)
            window.quick_expander.set_expanded(True)
            check("pinned & recent expands again", window.store.state.quick_expanded is True)
            from gi.repository import Gtk as _Gtk

            theme = _Gtk.IconTheme.get_for_display(window.get_display())
            recolorable = all(
                theme.has_icon(name)
                and theme.lookup_icon(name, None, 16, 1, _Gtk.TextDirection.LTR, 0).is_symbolic()
                for name in ("tag-symbolic", "network-workgroup-symbolic")
            )
            check("tags and graph icons recolor with the theme", recolorable)
            start_book()
            return False

        GLib.timeout_add(1500, check_highlight)

    def start_book():
        window._start_book("Book")
        wait_paged(0, check_book_open, "book pages are printed and shown")

    def wait_paged(tries, then, label):
        if window._paged_active():
            then()
            return False
        if tries > 18:
            check(label, False)
            finish_book()
            return False
        GLib.timeout_add(700, wait_paged, tries + 1, then, label)
        return False

    book_state = {}

    def check_book_open():
        check("book pages are printed and shown", True)
        check("book mode enters reading mode", getattr(window, "_zen", False))
        check("book opens at the first chapter", window.current_note == "Book/01 One.md")
        check("the chapter prints to multiple pages", window.paged_view.count > 1)
        page_w = window.paged_view.document.get_page(0).get_size()[0]
        check("the printed page keeps a book measure", page_w <= 880 * 72 / 96 + 1)
        strip = window.paged_view.indicator.get_parent() is window.paged_view
        check("the place indicator has its own strip", strip)
        book_state["one_pages"] = window.paged_view.count
        page = window._provide_page("/note/Book/01 One.md", window.reader.webview)
        navigated = 'class="book-nav"' in page and "1 of 3" in page
        check("chapter page carries the book nav", navigated)
        check("book page drops the vault machinery", 'class="crumbs"' not in page)
        titled = window._provide_page("/note/Book/02 Two.md", window.reader.webview)
        check("frontmatter title names the chapter", ">The Middle Way</h1>" in titled)
        window.paged_view.turn(1)
        page_turned = window.paged_view.index == 1 and window.current_note == "Book/01 One.md"
        check("a turn moves one page, not one chapter", page_turned)
        window.paged_view.index = window.paged_view.count - 1
        window.paged_view.turn(1)
        wait_paged_chapter(0)
        return False

    def wait_paged_chapter(tries):
        arrived = (
            window.current_note == "Book/02 Two.md"
            and window._paged_active()
            and window.paged_view.index == 0
        )
        if arrived:
            check("the last page turns into the next chapter", True)
            saved = window.store.state.book_progress.get("Book") == "Book/02 Two.md"
            check("reading progress is remembered", saved)
            window.paged_view.turn(-1)
            wait_paged_back(0)
            return False
        if tries > 18:
            check("the last page turns into the next chapter", False)
            finish_book()
            return False
        GLib.timeout_add(700, wait_paged_chapter, tries + 1)
        return False

    def wait_paged_back(tries):
        landed = (
            window.current_note == "Book/01 One.md"
            and window._paged_active()
            and window.paged_view.index == window.paged_view.count - 1
        )
        if landed:
            check("turning back lands on the previous chapter's last page", True)
            finish_book()
            return False
        if tries > 18:
            check("turning back lands on the previous chapter's last page", False)
            finish_book()
            return False
        GLib.timeout_add(700, wait_paged_back, tries + 1)
        return False

    def finish_book():
        window._set_zen(False)
        check("closing the book leaves book mode", window.book is None)
        hidden = window.paged_view is None or not window.paged_view.get_visible()
        check("closing the book puts the pages away", hidden)
        page = window._provide_page("/note/Book/01 One.md", window.reader.webview)
        check("outside the book the page is a note again", 'class="book-nav"' not in page)
        window.reader.load_note("A.md")
        GLib.timeout_add(1200, lambda: (check_fidelity(), False)[1])
        return False

    def check_fidelity():
        rendered = window.reader.last_render
        check("math renders as MathML", rendered is not None and "<math" in rendered.body)
        canvas_page = window.renderer.render_canvas("Board.canvas")
        cards = canvas_page.count('class="canvas-card')
        check("canvas renders cards and edges", cards == 2 and "<line" in canvas_page)
        check("canvas links resolve to notes", "reader:///note/A.md" in canvas_page)
        window.reader.load_note("Board.canvas")

        def check_canvas_route():
            check("canvas opens in the reading pane", window.current_note == "Board.canvas")
            action = window.lookup_action("line-width")
            action.change_state(GLib.Variant.new_string("narrow"))
            page = window._provide_page("/note/A.md", window.reader.webview)
            check("typography override reaches the page", "max-width: 35rem" in page)
            check_pdf_preview()
            return False

        GLib.timeout_add(1200, check_canvas_route)

    def check_pdf_preview():
        import cairo

        from solander.gui.pdfview import PdfWindow, poppler_available

        check("poppler bindings are available", poppler_available())
        pdf_path = vault_path / "doc.pdf"
        surface = cairo.PDFSurface(str(pdf_path), 300, 200)
        context = cairo.Context(surface)
        for page_number in range(2):
            context.set_source_rgb(0, 0, 0)
            context.rectangle(40, 40, 120, 60)
            context.fill()
            if page_number == 0:
                context.move_to(40, 140)
                context.show_text("READABLEPAGETEXT")
            context.show_page()
        surface.finish()
        viewer = PdfWindow(pdf_path, window)
        check("pdf viewer parsed both pages", viewer.status.get_text() == "2 pages")
        rendered = viewer._surface(0)
        check("pdf page renders to a surface", rendered is not None and rendered.get_width() > 0)
        has_ink = False
        if rendered is not None:
            data = bytes(rendered.get_data())
            has_ink = any(data[i] < 200 for i in range(0, len(data), 4))
        check("pdf page has actual content", has_ink)
        viewer._describe_page(0)
        described = getattr(viewer._areas[0], "page_text", "")
        check("a PDF page's text reaches assistive technology", "READABLEPAGETEXT" in described)
        viewer.destroy()
        continue_pdf()

    def continue_pdf():
        appearance = window.lookup_action("appearance")
        window._on_appearance(appearance, GLib.Variant.new_string("dark"))
        window.reader.load_note("A.md")
        GLib.timeout_add(1500, do_export)

    def do_export():
        import tempfile

        from gi.repository import Gio

        pdf_path = Path(tempfile.mkdtemp()) / "export.pdf"
        window._export_pdf_to(Gio.File.new_for_path(str(pdf_path)))

        def check_pdf():
            written = pdf_path.exists() and pdf_path.read_bytes()[:5] == b"%PDF-"
            check("PDF export wrote a real PDF", written)
            if written:
                check_export_quality(pdf_path)
            export_split_note()
            return False

        GLib.timeout_add(2500, check_pdf)
        return False

    def export_split_note():
        import tempfile

        from gi.repository import Gio

        blocks = "\n\n".join(
            f"```text\nB{n}START\n"
            + "\n".join(f"line {n}-{i}" for i in range(25))
            + f"\nB{n}END\n```"
            for n in range(8)
        )
        (vault_path / "Split.md").write_text(f"# Split\n\n{blocks}\n")
        window.reader.load_note("Split.md")
        split_pdf = Path(tempfile.mkdtemp()) / "split.pdf"

        def do_split_export():
            window._export_pdf_to(Gio.File.new_for_path(str(split_pdf)))
            GLib.timeout_add(2500, check_split)
            return False

        def check_split():
            import gi

            gi.require_version("Poppler", "0.18")
            from gi.repository import Gio as gio
            from gi.repository import Poppler

            uri = gio.File.new_for_path(str(split_pdf)).get_uri()
            document = Poppler.Document.new_from_file(uri, None)
            page_of = {}
            for index in range(document.get_n_pages()):
                for word in document.get_page(index).get_text().split():
                    page_of.setdefault(word, index)
            check("split export spans several pages", document.get_n_pages() >= 2)
            whole = all(
                page_of.get(f"B{n}START") is not None
                and page_of.get(f"B{n}START") == page_of.get(f"B{n}END")
                for n in range(8)
            )
            check("no code block is split across a page boundary", whole)
            toggle = window.lookup_action("toggle-source")
            window._on_toggle_source(toggle, GLib.Variant.new_boolean(True))
            def done() -> bool:
                """The last callback in the chain: the run got all the way here.

                It closes the window as a person would, so the run also covers
                the session being saved on the way out.
                """
                finished.append(True)
                window.close()
                return False

            def check_board_width() -> bool:
                # His saved window: 1872 wide at 140% zoom, measured with the sidebar open.
                source = window.lookup_action("toggle-source")
                window._on_toggle_source(source, GLib.Variant.new_boolean(False))
                window.set_default_size(1872, 1045)
                window.sidebar_widget.set_visible(True)
                window.reader.webview.set_zoom_level(1.4)
                window.reader.load_note("Wide.md")

                def measure(tries: int = 0) -> bool:
                    # A new default size reaches a window that is already open only
                    # when the compositor gets to it, so the board waits for the width.
                    if window.get_width() != 1872 and tries < 20:
                        window.set_default_size(1872, 1045)
                        GLib.timeout_add(250, measure, tries + 1)
                        return False
                    script = (
                        "(() => { const k = document.querySelector('.kanban');"
                        " if (!k) return 'none';"
                        " const edge = k.getBoundingClientRect().right;"
                        " const r = [...k.querySelectorAll('.kanban-column')]"
                        ".map(c => c.getBoundingClientRect());"
                        " const past = Math.max(...r.map(b => b.right - edge));"
                        " const page = document.documentElement;"
                        " return [past.toFixed(1), Math.round(Math.min(...r.map(b => b.width))),"
                        " r.length, page.scrollWidth - page.clientWidth, window.innerWidth]"
                        ".join(','); })()"
                    )

                    def measured(webview, result) -> None:
                        value = webview.evaluate_javascript_finish(result).to_string()
                        print(
                            "   six-lane board: past the edge, narrowest, lanes,"
                            f" page overflow, page width = {value}"
                        )
                        check("the window reached the saved width", window.get_width() == 1872)
                        parts = value.split(",")
                        whole = len(parts) == 5
                        # Half a pixel covers lanes laid out at fractional widths.
                        check("a six-lane board fits its page with no sideways scroll",
                              whole and float(parts[0]) <= 0.5 and parts[2] == "6"
                              and int(parts[3]) <= 0)
                        check("its narrowest lane is still readable (at least 144 CSS px)",
                              whole and int(parts[1]) >= 144)
                        GLib.timeout_add(300, done)

                    # A world of its own, because the page's policy forbids scripts in the document.
                    webview = window.reader.webview
                    webview.evaluate_javascript(script, -1, "smoke", None, None, measured)
                    return False

                GLib.timeout_add(2000, measure)
                return False

            GLib.timeout_add(1200, check_board_width)
            return False

        GLib.timeout_add(1500, do_split_export)

    def check_export_quality(pdf_path):
        import cairo
        import gi

        gi.require_version("Poppler", "0.18")
        from gi.repository import Gio as gio
        from gi.repository import Poppler

        uri = gio.File.new_for_path(str(pdf_path)).get_uri()
        document = Poppler.Document.new_from_file(uri, None)
        text = "".join(
            document.get_page(i).get_text() for i in range(document.get_n_pages())
        )
        check("export keeps the tail of an overflowing code line", "ENDOFLONGLINE" in text)
        page = document.get_page(0)
        width, height = page.get_size()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(width), int(height))
        context = cairo.Context(surface)
        context.set_source_rgb(1, 1, 1)
        context.paint()
        page.render_for_printing(context)
        stride = surface.get_stride()
        data = bytes(surface.get_data())
        # Backgrounds are not printed, so a dark-theme export means light-gray
        # text on white paper. Sample the pixels of one known word, not the whole
        # page, since borders are dark in every theme and would mask pale text.
        rects = page.find_text("ENDOFLONGLINE")
        darkest = 255
        for rect in rects:
            top = int(height - rect.y2)
            bottom = int(height - rect.y1)
            for row in range(max(0, top), min(int(height), bottom)):
                for column in range(max(0, int(rect.x1)), min(int(width), int(rect.x2))):
                    darkest = min(darkest, data[row * stride + column * 4])
        check("export text ink is dark even from the dark theme", bool(rects) and darkest < 100)

    GLib.timeout_add(1500, after_navigation)
    return False


def write_extra_fixtures() -> None:
    """Fixture files for the 1.0 surfaces, written before the vault opens."""
    import json

    (vault_path / "Sub").mkdir(exist_ok=True)
    (vault_path / "Sub" / "Inside.md").write_text("# Inside\n")
    (vault_path / "Long.md").write_text(
        "# Long\n\n## First\n\ntext\n\n## Second\n\ntext\n\n## Third\n\ntext\n"
    )
    (vault_path / "Book").mkdir(exist_ok=True)
    (vault_path / "Book" / "01 One.md").write_text(
        "First prose here.\n\n" + ("A long paragraph of book prose, made to fill "
        "many printed pages so the paged reader has something to turn. " * 4 + "\n\n") * 120
    )
    (vault_path / "Book" / "02 Two.md").write_text(
        "---\ntitle: The Middle Way\n---\nSecond prose here.\n"
    )
    (vault_path / "Book" / "03 Three.md").write_text("Last prose here.\n")
    (vault_path / "Blocks.md").write_text(
        "# Blocks\n\n" + "A paragraph that only takes up room.\n\n" * 80
        + "The paragraph a link points at. ^deep\n\n" + "After it.\n\n" * 5
    )
    (vault_path / "Linker.md").write_text("Go to [[Blocks#^deep]].\n")
    (vault_path / "Flow.md").write_text(
        "# Flow\n\n```mermaid\nflowchart LR\n  A[start] -->|go| B{ok?}\n"
        "  B -->|yes| C[done]\n  style C stroke:#080\n```\n\n"
        "```mermaid\ngantt\n  title X\n```\n"
    )
    (vault_path / "Sprint.md").write_text(
        "---\nkanban-plugin: board\n---\n\n## Todo\n\n- [ ] [[A|card one]]\n\n"
        "## Done\n\n- [x] finished\n"
    )
    lanes = "".join(
        f"## Lane {n}\n\n- [ ] a card with enough words in it to wrap onto two lines\n\n"
        for n in range(6)
    )
    (vault_path / "Wide.md").write_text(f"---\nkanban-plugin: board\n---\n\n{lanes}")
    drawing = json.dumps({"elements": [
        {"type": "rectangle", "x": 0, "y": 0, "width": 80, "height": 40},
        {"type": "text", "x": 8, "y": 8, "width": 60, "height": 18, "text": "box"},
    ]})
    (vault_path / "Draw.excalidraw.md").write_text(
        f"---\nexcalidraw-plugin: parsed\n---\n\n```json\n{drawing}\n```\n"
    )
    (vault_path / "Things.base").write_text(
        'views:\n  - type: table\n    name: All\n    filters:\n      and:\n'
        '        - file.hasProperty("mood")\n    order:\n      - file.name\n      - mood\n'
    )
    snippets = vault_path / ".obsidian" / "snippets"
    snippets.mkdir(parents=True, exist_ok=True)
    (snippets / "test.css").write_text(
        ".note { border-top: 3px solid teal; } .evil { background: url(http://x/y.png); }"
    )
    (vault_path / ".obsidian" / "appearance.json").write_text(
        json.dumps({"enabledCssSnippets": ["test"]})
    )


def check_setup_window() -> None:
    """The GUI setup flow must stay up as a window instead of dying to stderr."""
    import os
    import signal
    import subprocess
    import time

    env = dict(os.environ, SOLANDER_FORCE_SETUP="1")
    process = subprocess.Popen(
        [sys.executable, "-m", "solander.cli"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    alive = process.poll() is None
    check("sandbox refusal opens the setup window", alive)
    if alive:
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)


PANEL_NAMES = {"Files", "Search", "Links", "Tags", "Bookmarks", "Graph"}


def check_saved_session() -> None:
    """Closing the window wrote how far down each open note was read."""
    import json
    import os

    config = Path(os.environ.get("XDG_CONFIG_HOME", "")) / "solander" / "session.json"
    try:
        saved = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    positions = saved.get("scroll_positions")
    print(f"   saved scroll positions: {len(positions or {})}")
    check("closing the window saves each open note's reading position", bool(positions))


def main() -> int:
    write_extra_fixtures()
    sys.excepthook = record_crash
    app = ReaderApplication()
    # Without this, a reader already running for the real vault owns the app id,
    # activate is forwarded to it, and zero checks would read as a pass.
    app.set_flags(app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)

    def kick_off(application):
        window = application.get_active_window()
        window.open_path(vault_path)
        wait_for_first_note(application, 0)
        GLib.timeout_add_seconds(WATCHDOG_SECONDS, give_up, application)

    def wait_for_first_note(application, tries: int) -> bool:
        """Starts the checks once a note is on screen, rather than after a guess.

        A fixed delay is a bet on how loaded the machine is, and it flapped: the
        first two checks failed on a run that was otherwise identical to a pass.
        Waiting on the condition removes the flap without hiding a real failure:
        past the bound the checks run anyway and report what they find.
        """
        window = application.get_active_window()
        shown = window is not None and window.current_note and window.reader.last_render
        ready = shown and tries >= FIRST_NOTE_FLOOR_TRIES
        if ready or tries >= FIRST_NOTE_TRIES:
            run_checks(application)
            return False
        GLib.timeout_add(FIRST_NOTE_POLL_MS, wait_for_first_note, application, tries + 1)
        return False

    def give_up(application) -> bool:
        """Ends a run whose chain of callbacks stopped, so the verdict is reached."""
        application.quit()
        return False

    app.connect_after("activate", kick_off)
    app.run([sys.argv[0]])
    check_setup_window()
    if not checks_run:
        print("RESULT: FAIL (no checks ran)")
        return 1
    # A chain that stopped early leaves every check after it unwritten, which is
    # indistinguishable from a run that had less to do.
    check("the run reached its last check", bool(finished))
    check_saved_session()
    print("RESULT:", "FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
