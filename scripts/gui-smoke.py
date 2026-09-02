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
            check("vault css snippet is applied sanitized", "teal" in page and "url(" not in page)
            inside = window._provide_page("/note/Sub/Inside.md", window.reader.webview)
            crumb = "reader:///action/reveal-folder?arg=Sub" in inside
            check("nested note header carries the breadcrumb", crumb)
            one_title = (
                '<h1 class="inline-title">Inside</h1>' in inside
                and inside.count(">Inside</h1>") == 1
            )
            check("a duplicate body H1 yields to the header title", one_title)
            second = window._provide_page("/note/Second Note.md", window.reader.webview)
            titled = '<h1 class="inline-title">Second Note</h1>' in second
            check("inline title shows when the body has none", titled)
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
            flow = window._provide_page("/note/Flow.md", window.reader.webview)
            drew = 'class="mermaid-diagram"' in flow and "start" in flow and "ok?" in flow
            check("mermaid flowchart renders as static SVG", drew)
            check("author stroke styling reaches the diagram", 'style="stroke:#080"' in flow)
            labeled = "gantt diagrams are not supported" in flow
            check("unsupported mermaid kinds name themselves", labeled)
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
            theme_action.change_state(GLib.Variant.new_string("atelier"))
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
            from obsidian_reader.core.search import search_filenames

            names = [node.rel for node in window.tree._list_directory("")]
            check("tree lists the soon-hidden folder", "Sub" in names)
            key = str(window.vault.root)
            window.store.state.hidden_folders[key] = ["Sub"]
            window._apply_hidden_folders()
            names = [node.rel for node in window.tree._list_directory("")]
            hits = window._visible_hits(search_filenames(window.vault, "inside"))
            check("hidden folder leaves the tree", "Sub" not in names)
            check("hidden folder leaves quick-open", all("Sub/" not in h.path for h in hits))
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
            window._show_mindmap()
            GLib.timeout_add(1000, check_map_toggle_on)
            return False

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

        from obsidian_reader.gui.pdfview import PdfWindow, poppler_available

        check("poppler bindings are available", poppler_available())
        pdf_path = vault_path / "doc.pdf"
        surface = cairo.PDFSurface(str(pdf_path), 300, 200)
        context = cairo.Context(surface)
        for _page in range(2):
            context.set_source_rgb(0, 0, 0)
            context.rectangle(40, 40, 120, 60)
            context.fill()
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
            GLib.timeout_add(1200, lambda: (app.quit(), False)[1])
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
        # page — borders are dark in every theme and would mask pale text.
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
    (vault_path / "Flow.md").write_text(
        "# Flow\n\n```mermaid\nflowchart LR\n  A[start] -->|go| B{ok?}\n"
        "  B -->|yes| C[done]\n  style C stroke:#080\n```\n\n"
        "```mermaid\ngantt\n  title X\n```\n"
    )
    (vault_path / "Sprint.md").write_text(
        "---\nkanban-plugin: board\n---\n\n## Todo\n\n- [ ] [[A|card one]]\n\n"
        "## Done\n\n- [x] finished\n"
    )
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

    env = dict(os.environ, OBSIDIAN_READER_FORCE_SETUP="1")
    process = subprocess.Popen(
        [sys.executable, "-m", "obsidian_reader.cli"],
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


def main() -> int:
    write_extra_fixtures()
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
    check_setup_window()
    if not checks_run:
        print("RESULT: FAIL (no checks ran)")
        return 1
    print("RESULT:", "FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
