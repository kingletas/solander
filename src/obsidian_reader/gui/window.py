"""The main window: sidebar, reading pane, search, and every user-facing state."""

import html
import threading
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
import hashlib
import os
import sqlite3

from gi.repository import Adw, Gio, GLib, Gtk, WebKit

from .. import APP_ID, APP_NAME, __version__
from ..core.bookmarks import read_bookmarks
from ..core.graph import VaultGraph, local_neighbors
from ..core.indexing import sync_indexes
from ..core.render import NoteRenderer, build_message_page, build_page, build_source_page
from ..core.resolver import resolve_note
from ..core.search import VaultSearch, parse_query, search_filenames
from ..core.session import SessionStore
from ..core.store import open_index_store
from ..core.vault import Vault, file_kind
from .filetree import VaultTree
from .localgraph import LocalGraphView
from .monitor import VaultMonitor
from .webpane import ReaderView

MAX_AMBIGUOUS_CHOICES = 8
MAX_PANEL_ROWS = 200
HOVER_PREVIEW_DELAY_MS = 600

SHORTCUTS = [
    ("Ctrl+O", "Open file"),
    ("Ctrl+Shift+O", "Open vault folder"),
    ("Ctrl+F", "Find within note"),
    ("Ctrl+Shift+F", "Search the vault"),
    ("Ctrl+P", "Quick open"),
    ("Ctrl+R", "Reload current note"),
    ("Ctrl+U", "Toggle raw source view"),
    ("Alt+Left / Alt+Right", "Back / Forward"),
    ("Ctrl+T / Ctrl+W", "New tab / Close tab"),
    ("Middle-click or Ctrl+click", "Open note or link in a new tab"),
    ("F9", "Toggle sidebar"),
    ("F11", "Reading mode (Esc leaves)"),
    ("Ctrl+Shift+E", "Export as PDF"),
    ("Ctrl++ / Ctrl+- / Ctrl+0", "Zoom in / out / reset"),
    ("Ctrl+?", "This window"),
]


class ReaderWindow(Adw.ApplicationWindow):
    """One vault, one reading surface, and no way to write into either."""

    def __init__(self, application):
        super().__init__(application=application, title=APP_NAME)
        self.store = SessionStore()
        self.vault: Vault | None = None
        self.renderer: NoteRenderer | None = None
        self.search_index: VaultSearch | None = None
        self.graph: VaultGraph | None = None
        self.index_store = None
        self.vault_monitor: VaultMonitor | None = None
        self._sync_lock = threading.Lock()
        self._sync_pending = False
        self.current_note = ""
        self.source_view = False
        self.monitor = None
        self._preview_reader = None
        self._preview_timeout = 0
        self._preview_pending = ""
        self._pending_highlight = ""
        self._pointer = (0.0, 0.0)
        self.set_default_size(self.store.state.window_width, self.store.state.window_height)
        self._apply_appearance(self.store.state.appearance)
        self._build_ui()
        self._install_actions()

    # -- construction ------------------------------------------------------

    @property
    def reader(self) -> ReaderView:
        """The ReaderView of the selected tab; a first tab is created on demand."""
        page = self.tab_view.get_selected_page()
        if page is None:
            return self._create_tab()
        return self._readers[page.get_child()]

    def _create_reader(self) -> ReaderView:
        reader = ReaderView(share_from=self._first_reader)
        if self._first_reader is None:
            reader.page_provider = self._provide_page
            reader.asset_provider = self._provide_asset
            self._first_reader = reader
        reader.connect("open-external-uri", self._on_external_uri)
        reader.connect("open-external-file", self._on_external_file)
        reader.connect("choose-ambiguous", self._on_ambiguous)
        reader.connect("run-action", self._on_page_action)
        reader.connect("hover-link", self._on_hover_link)
        reader.connect("navigate-note-new-tab", self._on_navigate_new_tab)
        reader.webview.connect("load-changed", self._on_load_changed)
        reader.webview.set_zoom_level(self.store.state.zoom)
        reader.webview.set_vexpand(True)
        self._readers[reader.webview] = reader
        return reader

    def _create_tab(self, select: bool = True) -> ReaderView:
        """Adds a tab holding a fresh ReaderView and optionally selects it."""
        reader = self._create_reader()
        page = self.tab_view.append(reader.webview)
        page.set_title("New Tab")
        if select:
            self.tab_view.set_selected_page(page)
        return reader

    def open_in_new_tab(self, rel: str, anchor: str = "") -> None:
        """Opens a note in a new selected tab."""
        reader = self._create_tab()
        reader.load_note(rel, anchor)

    def _on_navigate_new_tab(self, _reader, rel: str, anchor: str) -> None:
        self.open_in_new_tab(rel, anchor)

    def _build_ui(self) -> None:
        self._readers: dict = {}
        self._first_reader = None
        self.tab_view = Adw.TabView()
        self.tab_view.connect("notify::selected-page", lambda *_: self._sync_chrome())
        self.tab_view.connect("close-page", self._on_close_page)
        self.tab_view.connect("page-detached", self._on_page_detached)

        header = Adw.HeaderBar()
        self.title_widget = Adw.WindowTitle(title=APP_NAME, subtitle="")
        header.set_title_widget(self.title_widget)

        open_menu = Gio.Menu()
        open_menu.append("Open File…", "win.open-file")
        open_menu.append("Open Vault Folder…", "win.open-vault")
        self.recents_section = Gio.Menu()
        open_menu.append_section("Recent vaults", self.recents_section)
        open_button = Gtk.MenuButton(icon_name="document-open-symbolic", menu_model=open_menu)
        open_button.set_tooltip_text("Open a file or vault")
        header.pack_start(open_button)

        self.back_button = Gtk.Button(icon_name="go-previous-symbolic", sensitive=False)
        self.back_button.set_tooltip_text("Back (Alt+Left)")
        self.back_button.connect("clicked", lambda *_: self.reader.webview.go_back())
        self.forward_button = Gtk.Button(icon_name="go-next-symbolic", sensitive=False)
        self.forward_button.set_tooltip_text("Forward (Alt+Right)")
        self.forward_button.connect("clicked", lambda *_: self.reader.webview.go_forward())
        header.pack_start(self.back_button)
        header.pack_start(self.forward_button)

        readonly = Gtk.Box(spacing=4)
        readonly.append(Gtk.Image(icon_name="changes-prevent-symbolic"))
        readonly.append(Gtk.Label(label="Read-only"))
        readonly.add_css_class("readonly-pill")
        readonly.set_tooltip_text("This vault is opened read-only; nothing is ever written into it")
        header.pack_end(self._main_menu_button())
        header.pack_end(readonly)
        self.outline_button = self._outline_button()
        header.pack_end(self.outline_button)
        search_button = Gtk.Button(icon_name="system-search-symbolic")
        search_button.set_tooltip_text("Search the vault (Ctrl+Shift+F)")
        search_button.connect("clicked", lambda *_: self._show_search())
        header.pack_end(search_button)

        self.sidebar_widget = self._build_sidebar()
        self.sidebar_widget.set_visible(self.store.state.sidebar_visible)
        self.paned = Gtk.Paned(
            orientation=Gtk.Orientation.HORIZONTAL,
            position=self.store.state.sidebar_width,
            shrink_start_child=False,
            resize_start_child=False,
        )
        self.paned.set_start_child(self.sidebar_widget)
        self.paned.set_end_child(self._build_content())

        self.toolbar_view = Adw.ToolbarView()
        self.toolbar_view.add_top_bar(header)
        self.toolbar_view.set_content(self.paned)
        self.toasts = Adw.ToastOverlay(child=self.toolbar_view)
        self.set_content(self.toasts)
        self.connect("close-request", self._on_close)
        self._install_drop_target()
        self._load_css()
        self._refresh_recents_menu()
        self._create_tab()

    def _build_sidebar(self) -> Gtk.Widget:
        self._install_bundled_icons()
        self.sidebar_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)

        self.tree = VaultTree(self._on_tree_activate, self._on_tree_open_new_tab)
        self.tree.show_hidden = self.store.state.show_hidden
        self.tree.markdown_only = self.store.state.markdown_only
        tree_scroll = Gtk.ScrolledWindow(child=self.tree.view, vexpand=True)
        self._add_sidebar_page(tree_scroll, "files", "Files", "folder-symbolic")

        search_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        search_box.set_margin_top(6)
        self.search_entry = Gtk.SearchEntry(placeholder_text="Search — words, path:, file:, tag:")
        self.search_entry.set_margin_start(6)
        self.search_entry.set_margin_end(6)
        self.search_entry.connect("search-changed", self._on_search_typed)
        self.search_entry.connect("activate", self._on_search_submitted)
        self.search_results = Gtk.ListBox()
        self.search_results.add_css_class("navigation-sidebar")
        self.search_results.connect("row-activated", self._on_search_row)
        self.search_status = Gtk.Label(xalign=0.0, wrap=True)
        self.search_status.add_css_class("dim-label")
        self.search_status.set_margin_start(10)
        results_scroll = Gtk.ScrolledWindow(child=self.search_results, vexpand=True)
        search_box.append(self.search_entry)
        search_box.append(self.search_status)
        search_box.append(results_scroll)
        self._add_sidebar_page(search_box, "search", "Search", "edit-find-symbolic")

        self.links_list = Gtk.ListBox()
        self.links_list.add_css_class("navigation-sidebar")
        self.links_list.connect("row-activated", self._on_panel_row)
        links_scroll = Gtk.ScrolledWindow(child=self.links_list, vexpand=True)
        self._add_sidebar_page(links_scroll, "links", "Links", "insert-link-symbolic")

        tags_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        tags_box.set_margin_top(6)
        self.tag_filter = Gtk.SearchEntry(placeholder_text="Filter tags…")
        self.tag_filter.set_margin_start(6)
        self.tag_filter.set_margin_end(6)
        self.tag_filter.connect("search-changed", self._refresh_tags_panel)
        self.tags_list = Gtk.ListBox()
        self.tags_list.add_css_class("navigation-sidebar")
        self.tags_list.connect("row-activated", self._on_tag_row)
        tags_box.append(self.tag_filter)
        tags_box.append(Gtk.ScrolledWindow(child=self.tags_list, vexpand=True))
        self._add_sidebar_page(tags_box, "tags", "Tags", "reader-tag-symbolic")

        self.bookmarks_list = Gtk.ListBox()
        self.bookmarks_list.add_css_class("navigation-sidebar")
        self.bookmarks_list.connect("row-activated", self._on_panel_row)
        bookmarks_scroll = Gtk.ScrolledWindow(child=self.bookmarks_list, vexpand=True)
        self._add_sidebar_page(
            bookmarks_scroll, "bookmarks", "Bookmarks", "user-bookmarks-symbolic"
        )

        self.local_graph = LocalGraphView(lambda rel: self.reader.load_note(rel))
        self._add_sidebar_page(self.local_graph.area, "graph", "Graph", "reader-graph-symbolic")

        switcher = Gtk.StackSwitcher(stack=self.sidebar_stack)
        switcher.set_margin_top(6)
        switcher.set_halign(Gtk.Align.CENTER)

        self.index_status = Gtk.Label(xalign=0.0)
        self.index_status.add_css_class("dim-label")
        self.index_status.set_margin_start(10)
        self.index_status.set_margin_bottom(6)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(switcher)
        box.append(self.sidebar_stack)
        box.append(self.index_status)
        return box

    def _add_sidebar_page(self, child, name: str, title: str, icon: str) -> None:
        page = self.sidebar_stack.add_titled(child, name, title)
        page.set_icon_name(icon)

    def _install_bundled_icons(self) -> None:
        """Adds the app's bundled symbolic icons to the icon search path."""
        from importlib import resources

        from gi.repository import Gdk

        display = Gdk.Display.get_default()
        if display is None:
            return
        icon_dir = resources.files("obsidian_reader.assets").joinpath("icons")
        Gtk.IconTheme.get_for_display(display).add_search_path(str(icon_dir))

    # -- sidebar panels ----------------------------------------------------

    def _clear_list(self, listbox: Gtk.ListBox) -> None:
        while (row := listbox.get_first_child()) is not None:
            listbox.remove(row)

    def _panel_header(self, text: str) -> Gtk.ListBoxRow:
        label = Gtk.Label(label=text, xalign=0.0)
        label.add_css_class("heading")
        label.set_margin_top(8)
        row = Gtk.ListBoxRow(child=label, activatable=False, selectable=False)
        return row

    def _panel_note(self, text: str) -> Gtk.ListBoxRow:
        label = Gtk.Label(label=text, xalign=0.0, wrap=True)
        label.add_css_class("dim-label")
        return Gtk.ListBoxRow(child=label, activatable=False, selectable=False)

    def _panel_row(
        self, title: str, caption: str = "", snippet: str = "", note_path: str = ""
    ) -> Gtk.ListBoxRow:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.append(Gtk.Label(label=title, xalign=0.0, ellipsize=3))
        if caption:
            caption_label = Gtk.Label(label=caption, xalign=0.0, ellipsize=2)
            caption_label.add_css_class("dim-label")
            caption_label.add_css_class("caption")
            box.append(caption_label)
        if snippet:
            snippet_label = Gtk.Label(label=snippet, xalign=0.0, wrap=True, lines=2, ellipsize=3)
            snippet_label.add_css_class("caption")
            box.append(snippet_label)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        row = Gtk.ListBoxRow(child=box)
        row.note_path = note_path
        if not note_path:
            row.set_activatable(False)
        return row

    def _on_panel_row(self, _list, row) -> None:
        path = getattr(row, "note_path", "")
        if path:
            self.reader.load_note(path)

    def _update_links_panel(self) -> None:
        """Rebuilds the Links page for the current note: linked mentions, then outgoing."""
        self._clear_list(self.links_list)
        if self.vault is None:
            self.links_list.append(self._panel_note("Open a vault first"))
            return
        if self.graph is None or not self.graph.ready:
            self.links_list.append(self._panel_note("Link index is still building…"))
            return
        rel = self.current_note
        if not rel:
            self.links_list.append(self._panel_note("Open a note to see its links"))
            return
        mentions = self.graph.backlinks.get(rel, [])
        self.links_list.append(self._panel_header(f"Linked mentions ({len(mentions)})"))
        for mention in mentions[:MAX_PANEL_ROWS]:
            title = mention.source.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            self.links_list.append(
                self._panel_row(title, mention.source, mention.context, mention.source)
            )
        if not mentions:
            self.links_list.append(self._panel_note("No notes link here"))
        outgoing = self.graph.outgoing.get(rel, [])
        self.links_list.append(self._panel_header(f"Outgoing links ({len(outgoing)})"))
        for link in outgoing[:MAX_PANEL_ROWS]:
            if link.kind == "note":
                title = link.path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                self.links_list.append(self._panel_row(title, link.path, "", link.path))
            else:
                state = "ambiguous" if link.kind == "ambiguous" else "not found"
                self.links_list.append(self._panel_note(f"{link.target} — {state}"))
        if not outgoing:
            self.links_list.append(self._panel_note("No outgoing links"))

    def _refresh_tags_panel(self, *_args) -> None:
        """Rebuilds the Tags page from the graph, filtered by the tag filter entry."""
        self._clear_list(self.tags_list)
        if self.graph is None or not self.graph.ready:
            self.tags_list.append(
                self._panel_note(
                    "Tag index is still building…" if self.vault else "Open a vault first"
                )
            )
            return
        needle = self.tag_filter.get_text().strip().lstrip("#").casefold()
        shown = 0
        for folded in sorted(self.graph.tags):
            if needle and needle not in folded:
                continue
            display = self.graph.tag_names[folded]
            count = len(self.graph.tags[folded])
            box = Gtk.Box(spacing=6)
            name = Gtk.Label(label=f"#{display}", xalign=0.0, ellipsize=2, hexpand=True)
            counter = Gtk.Label(label=str(count))
            counter.add_css_class("dim-label")
            counter.add_css_class("caption")
            box.append(name)
            box.append(counter)
            box.set_margin_top(3)
            box.set_margin_bottom(3)
            row = Gtk.ListBoxRow(child=box)
            row.tag_value = display
            self.tags_list.append(row)
            shown += 1
            if shown >= 500:
                break
        if shown == 0:
            self.tags_list.append(self._panel_note("No tags"))

    def _on_tag_row(self, _list, row) -> None:
        """Turns a tag row into a search: `tag:<name>` submitted on the Search page."""
        tag = getattr(row, "tag_value", "")
        if not tag:
            return
        self.search_entry.set_text(f"tag:{tag}")
        self.sidebar_stack.set_visible_child_name("search")
        self._on_search_submitted(self.search_entry)

    def _refresh_bookmarks_panel(self) -> None:
        """Rebuilds the Bookmarks page from the vault's own bookmarks file."""
        self._clear_list(self.bookmarks_list)
        if self.vault is None:
            self.bookmarks_list.append(self._panel_note("Open a vault first"))
            return
        bookmarks = read_bookmarks(self.vault)
        if not bookmarks:
            self.bookmarks_list.append(self._panel_note("No bookmarks in this vault"))
            return
        last_group = None
        for bookmark in bookmarks:
            if bookmark.group != last_group:
                if bookmark.group:
                    self.bookmarks_list.append(self._panel_header(bookmark.group))
                last_group = bookmark.group
            self.bookmarks_list.append(
                self._panel_row(bookmark.title, bookmark.rel, "", bookmark.rel)
            )

    def _build_content(self) -> Gtk.Widget:
        self.tab_bar = Adw.TabBar(view=self.tab_view, autohide=True)
        self.find_bar = Gtk.SearchBar()
        self.find_entry = Gtk.SearchEntry(placeholder_text="Find in note…")
        self.find_entry.connect("search-changed", self._on_find_changed)
        self.find_entry.connect("activate", self._on_find_next)
        self.find_entry.connect("stop-search", lambda *_: self.find_bar.set_search_mode(False))
        self.find_bar.set_child(self.find_entry)
        self.find_bar.connect_entry(self.find_entry)

        self.hover_label = Gtk.Label(xalign=0.0, ellipsize=2)
        self.hover_label.add_css_class("hover-status")
        self.hover_label.set_halign(Gtk.Align.START)
        self.hover_label.set_valign(Gtk.Align.END)
        self.hover_label.set_visible(False)

        self.tab_view.set_vexpand(True)
        overlay = Gtk.Overlay(child=self.tab_view)
        overlay.add_overlay(self.hover_label)
        self.content_overlay = overlay
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_pointer_motion)
        overlay.add_controller(motion)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.tab_bar)
        box.append(self.find_bar)
        box.append(overlay)
        return box

    def _main_menu_button(self) -> Gtk.MenuButton:
        menu = Gio.Menu()
        appearance = Gio.Menu()
        appearance.append("Follow System", "win.appearance::system")
        appearance.append("Light", "win.appearance::light")
        appearance.append("Dark", "win.appearance::dark")
        menu.append_submenu("Appearance", appearance)
        typography = Gio.Menu()
        fonts = Gio.Menu()
        for label, value in (
            ("Theme Default", "default"), ("Serif", "serif"), ("Sans", "sans"), ("Mono", "mono")
        ):
            fonts.append(label, f"win.reader-font::{value}")
        typography.append_submenu("Font", fonts)
        widths = Gio.Menu()
        for label, value in (
            ("Narrow", "narrow"), ("Normal", "normal"), ("Wide", "wide"), ("Full", "full")
        ):
            widths.append(label, f"win.line-width::{value}")
        typography.append_submenu("Line Width", widths)
        spacings = Gio.Menu()
        for label, value in (
            ("Compact", "compact"), ("Normal", "normal"), ("Relaxed", "relaxed")
        ):
            spacings.append(label, f"win.line-spacing::{value}")
        typography.append_submenu("Line Spacing", spacings)
        menu.append_submenu("Typography", typography)
        view = Gio.Menu()
        view.append("New Tab", "win.new-tab")
        view.append("Reading Mode", "win.zen")
        view.append("Raw Source View", "win.toggle-source")
        view.append("Show Hidden Files", "win.show-hidden")
        view.append("Markdown Files Only", "win.markdown-only")
        view.append("Restore Session on Launch", "win.restore-session")
        menu.append_section(None, view)
        note = Gio.Menu()
        note.append("Export as PDF…", "win.export-pdf")
        note.append("Reveal in Files", "win.reveal")
        note.append("Open Externally", "win.open-external")
        note.append("Copy Markdown Source", "win.copy-source")
        note.append("Copy Vault Path", "win.copy-path")
        note.append("Copy as Wikilink", "win.copy-wikilink")
        menu.append_section(None, note)
        meta = Gio.Menu()
        meta.append("Clear Index Cache", "win.clear-cache")
        meta.append("Keyboard Shortcuts", "win.shortcuts")
        meta.append(f"About {APP_NAME}", "win.about")
        menu.append_section(None, meta)
        button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        button.set_tooltip_text("Main menu")
        return button

    def _outline_button(self) -> Gtk.MenuButton:
        self.outline_list = Gtk.ListBox()
        self.outline_list.add_css_class("navigation-sidebar")
        self.outline_list.connect("row-activated", self._on_outline_row)
        scroll = Gtk.ScrolledWindow(
            child=self.outline_list, propagate_natural_height=True, max_content_height=500,
            propagate_natural_width=True, max_content_width=420,
        )
        popover = Gtk.Popover(child=scroll)
        button = Gtk.MenuButton(icon_name="view-list-symbolic", popover=popover, sensitive=False)
        button.set_tooltip_text("Outline")
        return button

    def _install_drop_target(self) -> None:
        from gi.repository import Gdk

        drop = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop.connect("drop", lambda _t, value, _x, _y: self._open_gfile(value) or True)
        self.add_controller(drop)

    def _load_css(self) -> None:
        from gi.repository import Gdk

        css = """
        .readonly-pill { background: alpha(currentColor, 0.1); border-radius: 999px;
                         padding: 2px 10px; font-size: 0.85em; }
        .hover-status { background: alpha(@window_bg_color, 0.9); border-radius: 6px;
                        padding: 2px 8px; margin: 6px; font-size: 0.85em; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # -- actions -----------------------------------------------------------

    def _install_actions(self) -> None:
        def add(name, callback, accels=(), parameter=None, state=None):
            if state is not None:
                action = Gio.SimpleAction.new_stateful(name, parameter, state)
                action.connect("change-state", callback)
            else:
                action = Gio.SimpleAction.new(name, parameter)
                action.connect("activate", callback)
            self.add_action(action)
            if accels:
                self.get_application().set_accels_for_action(f"win.{name}", list(accels))
            return action

        add("open-file", lambda *_: self._open_file_dialog(), ["<Control>o"])
        add("open-vault", lambda *_: self._open_vault_dialog(), ["<Control><Shift>o"])
        add("find", lambda *_: self._show_find(), ["<Control>f"])
        add("quick-open", lambda *_: self._show_search(), ["<Control>p"])
        add("search-vault", lambda *_: self._show_search(), ["<Control><Shift>f"])
        add("reload", lambda *_: self._reload(), ["<Control>r", "F5"])
        add("back", lambda *_: self.reader.webview.go_back(), ["<Alt>Left"])
        add("forward", lambda *_: self.reader.webview.go_forward(), ["<Alt>Right"])
        add("toggle-sidebar", lambda *_: self._toggle_sidebar(), ["F9"])
        add("new-tab", lambda *_: self._new_tab(), ["<Control>t"])
        add("close-tab", lambda *_: self._close_current_tab(), ["<Control>w"])
        add(
            "zen",
            self._on_zen,
            ["F11"],
            state=GLib.Variant.new_boolean(False),
        )
        self.leave_zen_action = add("leave-zen", lambda *_: self._set_zen(False), ["Escape"])
        self.leave_zen_action.set_enabled(False)
        add("export-pdf", lambda *_: self._export_pdf_dialog(), ["<Control><Shift>e"])
        add("zoom-in", lambda *_: self._zoom(0.1), ["<Control>plus", "<Control>equal"])
        add("zoom-out", lambda *_: self._zoom(-0.1), ["<Control>minus"])
        add("zoom-reset", lambda *_: self._zoom(None), ["<Control>0"])
        add("clear-cache", lambda *_: self._clear_index_cache())
        add("shortcuts", lambda *_: self._show_shortcuts(), ["<Control>question"])
        add("about", lambda *_: self._show_about())
        add("reveal", lambda *_: self._reveal_current())
        add("open-external", lambda *_: self._open_current_externally())
        add("copy-source", lambda *_: self._copy_current("source"))
        add("copy-path", lambda *_: self._copy_current("path"))
        add("copy-wikilink", lambda *_: self._copy_current("wikilink"))
        add(
            "toggle-source",
            self._on_toggle_source,
            ["<Control>u"],
            state=GLib.Variant.new_boolean(False),
        )
        add(
            "show-hidden",
            self._on_show_hidden,
            state=GLib.Variant.new_boolean(self.store.state.show_hidden),
        )
        add(
            "markdown-only",
            self._on_markdown_only,
            state=GLib.Variant.new_boolean(self.store.state.markdown_only),
        )
        add(
            "restore-session",
            self._on_restore_session,
            state=GLib.Variant.new_boolean(self.store.state.restore_session),
        )
        add(
            "appearance",
            self._on_appearance,
            parameter=GLib.VariantType.new("s"),
            state=GLib.Variant.new_string(self.store.state.appearance),
        )
        for name, key in (
            ("reader-font", "reader_font"),
            ("line-width", "line_width"),
            ("line-spacing", "line_spacing"),
        ):
            add(
                name,
                (lambda a, v, k=key: self._on_typography(a, v, k)),
                parameter=GLib.VariantType.new("s"),
                state=GLib.Variant.new_string(getattr(self.store.state, key)),
            )

    # -- opening things ----------------------------------------------------

    def open_path(self, path: Path) -> None:
        """Opens a directory as a vault, or a note file via its parent directory."""
        path = path.expanduser().resolve()
        if path.is_dir():
            self._open_vault(path)
        elif path.is_file():
            self.store.remember_file(str(path))
            self._open_vault(path.parent, focus_note=path.name)
        else:
            self._toast(f"No such file or folder: {path}")

    def restore_or_welcome(self) -> None:
        """Restores the previous session when enabled, otherwise shows the welcome page."""
        state = self.store.state
        if state.restore_session and state.last_vault and Path(state.last_vault).is_dir():
            self._open_vault(
                Path(state.last_vault), focus_note=state.last_note or None, restore_tabs=True
            )
        else:
            self.reader.load_page("welcome")

    def _open_vault(
        self, root: Path, focus_note: str | None = None, restore_tabs: bool = False
    ) -> None:
        self.index_status.set_text("Opening vault…")
        self.title_widget.set_subtitle(root.name)

        def build():
            vault = Vault.open(root)
            renderer = NoteRenderer(vault, self._typography)
            GLib.idle_add(self._vault_ready, vault, renderer, focus_note, restore_tabs)

        threading.Thread(target=build, daemon=True).start()

    def _close_extra_tabs(self) -> None:
        keep = self.tab_view.get_selected_page()
        extras = [
            self.tab_view.get_nth_page(i)
            for i in range(self.tab_view.get_n_pages())
            if self.tab_view.get_nth_page(i) is not keep
        ]
        for page in extras:
            self.tab_view.close_page(page)

    def _vault_ready(
        self,
        vault: Vault,
        renderer: NoteRenderer,
        focus_note: str | None,
        restore_tabs: bool = False,
    ) -> None:
        self.vault = vault
        self.renderer = renderer
        self.graph = None
        if self.vault_monitor is not None:
            self.vault_monitor.cancel()
        if self.index_store is not None:
            self.index_store.close()
        self.index_store = open_index_store(self._cache_path(vault.root))
        self.search_index = VaultSearch(self.index_store)
        self.vault_monitor = VaultMonitor(vault.root, self._schedule_sync)
        self.store.remember_vault(str(vault.root))
        self._refresh_recents_menu()
        self.tree.set_vault(vault.root)
        self._refresh_bookmarks_panel()
        self._refresh_tags_panel()
        self._update_links_panel()
        self.title_widget.set_subtitle(vault.root.name)
        self._close_extra_tabs()
        if not vault.notes:
            self.index_status.set_text("")
            self.reader.load_page("empty-vault")
        elif focus_note:
            resolved = resolve_note(vault, "", focus_note)
            if resolved.kind == "note":
                self.reader.load_note(resolved.path)
            elif vault.has_file(focus_note):
                self.reader.load_note(focus_note)
            else:
                self.reader.load_page("welcome")
        else:
            self.reader.load_note(vault.notes[0])
        if restore_tabs:
            current = self.store.state.last_note
            for rel in self.store.state.open_tabs:
                if rel != current and vault.has_file(rel):
                    background = self._create_tab(select=False)
                    background.load_note(rel)
        self._schedule_sync()
        return False

    # -- the live index ----------------------------------------------------

    def _cache_path(self, root: Path) -> Path:
        """One index file per vault, in the app's own cache dir — never the vault."""
        base = os.environ.get("XDG_CACHE_HOME", "") or str(Path.home() / ".cache")
        directory = Path(base) / "obsidian-reader"
        directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
        return directory / f"index-{digest}.db"

    def _schedule_sync(self) -> None:
        """Runs a background sync; overlapping requests coalesce into one more pass."""
        if self.vault is None:
            return
        threading.Thread(target=self._run_sync, args=(self.vault.root,), daemon=True).start()

    def _run_sync(self, root: Path) -> None:
        if not self._sync_lock.acquire(blocking=False):
            self._sync_pending = True
            return
        try:
            while True:
                self._sync_pending = False
                store = self.index_store
                search = self.search_index
                if store is None or search is None:
                    return

                def progress(done, total):
                    GLib.idle_add(self.index_status.set_text, f"Indexing {done}/{total}…")

                vault = Vault.open(root)
                renderer = NoteRenderer(vault, self._typography)
                try:
                    result = sync_indexes(vault, store, progress=progress)
                except sqlite3.Error:
                    # A corrupted cache is derived data: delete it and rebuild once.
                    store.close()
                    for suffix in ("", "-wal", "-shm"):
                        Path(f"{store.path}{suffix}").unlink(missing_ok=True)
                    self.index_store = store = open_index_store(store.path)
                    search.store = store
                    result = sync_indexes(vault, store, progress=progress)
                GLib.idle_add(self._apply_sync, vault, renderer, result.graph, search)
                if not self._sync_pending:
                    return
        finally:
            self._sync_lock.release()

    def _apply_sync(self, vault: Vault, renderer, graph: VaultGraph, search) -> bool:
        """Swaps in the freshly synced vault, renderer, and graph on the main loop."""
        if self.vault is None or vault.root != self.vault.root or search is not self.search_index:
            return False
        files_changed = vault.files != self.vault.files
        self.vault = vault
        self.renderer = renderer
        self.graph = graph
        search.ready = True
        self.index_status.set_text(f"{len(vault.notes)} notes · {len(graph.tags)} tags")
        if files_changed:
            self.tree.refresh()
            self._refresh_bookmarks_panel()
        self._refresh_tags_panel()
        self._update_links_panel()
        self._update_local_graph()
        return False

    def _typography(self) -> dict:
        """The reading-comfort settings the page shell injects as CSS overrides."""
        state = self.store.state
        return {
            "font": state.reader_font,
            "width": state.line_width,
            "spacing": state.line_spacing,
        }

    def _on_typography(self, action, value, key: str) -> None:
        action.set_state(value)
        setattr(self.store.state, key, value.get_string())
        self._reload_all_tabs()

    def _clear_index_cache(self) -> None:
        """Deletes the persistent index for this vault and rebuilds it from scratch."""
        if self.vault is None or self.index_store is None:
            return
        path = self.index_store.path
        self.index_store.close()
        for suffix in ("", "-wal", "-shm"):
            Path(f"{path}{suffix}").unlink(missing_ok=True)
        self.index_store = open_index_store(path)
        self.search_index = VaultSearch(self.index_store)
        self.graph = None
        self._schedule_sync()
        self._toast("Index cache cleared — rebuilding")

    def _open_file_dialog(self) -> None:
        dialog = Gtk.FileDialog(title="Open Markdown file")
        markdown_filter = Gtk.FileFilter()
        markdown_filter.set_name("Markdown files")
        markdown_filter.add_suffix("md")
        markdown_filter.add_suffix("markdown")
        filters = Gio.ListStore(item_type=Gtk.FileFilter)
        filters.append(markdown_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self._file_chosen)

    def _open_vault_dialog(self) -> None:
        Gtk.FileDialog(title="Open vault folder").select_folder(self, None, self._folder_chosen)

    def _file_chosen(self, dialog, result) -> None:
        try:
            self._open_gfile(dialog.open_finish(result))
        except GLib.Error:
            return

    def _folder_chosen(self, dialog, result) -> None:
        try:
            self._open_gfile(dialog.select_folder_finish(result))
        except GLib.Error:
            return

    def _open_gfile(self, gfile) -> None:
        if gfile is not None and gfile.get_path():
            self.open_path(Path(gfile.get_path()))

    # -- page and asset providers -----------------------------------------

    def _theme(self) -> str:
        return "dark" if Adw.StyleManager.get_default().get_dark() else "light"

    def _provide_page(self, path: str, webview=None) -> str:
        theme = self._theme()
        reader = self._readers.get(webview)
        segments = [part for part in path.split("/") if part]
        if segments and segments[0] == "note" and self.renderer is not None:
            rel = "/".join(segments[1:])
            if self.source_view:
                if reader is not None:
                    reader.last_render = None
                note = self.vault.read_note(rel)
                return build_source_page(note.text or note.error, rel, theme)
            if rel.casefold().endswith(".canvas"):
                if reader is not None:
                    reader.last_render = None
                return self.renderer.render_canvas(rel, theme)
            rendered = self.renderer.render(rel, theme)
            if reader is not None:
                reader.last_render = rendered
            return rendered.page
        if segments and segments[0] == "preview" and self.renderer is not None:
            return self.renderer.render_preview("/".join(segments[1:]), theme)
        if segments and segments[0] == "page":
            return self._app_page(segments[1] if len(segments) > 1 else "", theme)
        return ""

    def _app_page(self, name: str, theme: str) -> str:
        if name == "welcome":
            return self._welcome_page(theme)
        if name == "empty-vault":
            return build_message_page(
                "This vault has no Markdown notes",
                "The folder opened fine, but there is nothing here to read.",
                theme,
            )
        return build_message_page("Not found", f"No app page named {name}", theme)

    def _welcome_page(self, theme: str) -> str:
        recents = ""
        for root in self.store.state.recent_vaults:
            label = html.escape(root)
            href = f"reader:///action/open-recent?arg={quote(root, safe='')}"
            recents += f'<li><a href="{href}">{label}</a></li>'
        recents_block = f"<h2>Recent vaults</h2><ul>{recents}</ul>" if recents else ""
        body = (
            '<div class="message-state"><h1>Obsidian Reader</h1>'
            "<p>Open an existing vault or a single Markdown file. "
            "Everything is read-only: nothing is ever written into your vault.</p>"
            '<p><a href="reader:///action/open-vault">Open a vault folder…</a> · '
            '<a href="reader:///action/open-file">Open a file…</a></p>'
            f"{recents_block}</div>"
        )
        return build_page(body, APP_NAME, theme)

    def _provide_asset(self, rel: str):
        if self.vault is None or not self.vault.has_file(rel):
            return None
        if file_kind(rel) not in ("image", "audio", "video"):
            return None
        return self.vault.root / rel

    # -- navigation and rendering state ------------------------------------

    def _on_load_changed(self, webview, event) -> None:
        if event == WebKit.LoadEvent.FINISHED:
            # A note opened from a search result gets its matches highlighted.
            if self._pending_highlight and self.reader.webview is webview:
                options = WebKit.FindOptions.CASE_INSENSITIVE | WebKit.FindOptions.WRAP_AROUND
                webview.get_find_controller().search(self._pending_highlight, options, 500)
                self._pending_highlight = ""
            return
        if event != WebKit.LoadEvent.COMMITTED:
            return
        reader = self._readers.get(webview)
        if reader is None:
            return
        parsed = urlparse(webview.get_uri() or "")
        segments = [unquote(part) for part in parsed.path.split("/") if part]
        if parsed.scheme == "reader" and segments and segments[0] == "note":
            reader.current_note = "/".join(segments[1:])
        else:
            reader.current_note = ""
        page = self.tab_view.get_page(webview)
        if page is not None:
            title = reader.current_note.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            page.set_title(title or APP_NAME)
        selected = self.tab_view.get_selected_page()
        if selected is not None and selected.get_child() is webview:
            self._sync_chrome()

    def _sync_chrome(self) -> None:
        """Points every piece of window chrome at the selected tab's state."""
        page = self.tab_view.get_selected_page()
        if page is None:
            return
        reader = self._readers.get(page.get_child())
        if reader is None:
            return
        webview = reader.webview
        self.back_button.set_sensitive(webview.can_go_back())
        self.forward_button.set_sensitive(webview.can_go_forward())
        self.current_note = reader.current_note
        if reader.current_note:
            self.store.state.last_note = reader.current_note
            self.store.remember_note(reader.current_note)
            title = reader.current_note.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            self.title_widget.set_title(title)
            self.tree.select_path(reader.current_note)
            rendered = reader.last_render
            outline = rendered.outline if rendered is not None and rendered.title else []
            self._fill_outline(outline)
            if self.vault is not None:
                self._watch_current_note(self.vault.root / reader.current_note)
        else:
            self.outline_button.set_sensitive(False)
            self.title_widget.set_title(APP_NAME)
            self._watch_current_note(None)
        self._cancel_preview()
        self._update_links_panel()
        self._update_local_graph()

    def _update_local_graph(self) -> None:
        if self.graph is None or not self.current_note:
            self.local_graph.show_note("", [])
            return
        self.local_graph.show_note(
            self.current_note, local_neighbors(self.graph, self.current_note)
        )

    def _on_close_page(self, tab_view, page) -> bool:
        """Closes a tab; the last tab falls back to the welcome page instead."""
        if tab_view.get_n_pages() <= 1:
            reader = self._readers.get(page.get_child())
            if reader is not None:
                reader.load_page("welcome")
            tab_view.close_page_finish(page, False)
            return True
        tab_view.close_page_finish(page, True)
        return True

    def _on_page_detached(self, _tab_view, page, _position) -> None:
        self._readers.pop(page.get_child(), None)

    def _fill_outline(self, outline) -> None:
        while (row := self.outline_list.get_first_child()) is not None:
            self.outline_list.remove(row)
        for heading in outline:
            label = Gtk.Label(label=heading.text, xalign=0.0, ellipsize=3)
            label.set_margin_start((heading.level - 1) * 12)
            row = Gtk.ListBoxRow(child=label)
            row.anchor = heading.anchor
            self.outline_list.append(row)
        self.outline_button.set_sensitive(bool(outline))

    def _on_outline_row(self, _list, row) -> None:
        self.outline_button.get_popover().popdown()
        if self.current_note:
            self.reader.load_note(self.current_note, row.anchor)

    def _on_tree_activate(self, node) -> None:
        if node.is_note or file_kind(node.rel) == "canvas":
            self.reader.load_note(node.rel)
        elif file_kind(node.rel) in ("image", "audio", "video", "pdf"):
            self._launch_file(self.vault.root / node.rel)
        else:
            self._toast(f"{node.name} is not a text note — use Open Externally")

    def _on_tree_open_new_tab(self, node) -> None:
        if node.is_note:
            self.open_in_new_tab(node.rel)

    def _reload(self) -> None:
        if self.vault is not None:
            self._schedule_sync()
        self.reader.webview.reload()

    # -- search ------------------------------------------------------------

    def _show_search(self) -> None:
        self.sidebar_widget.set_visible(True)
        self.sidebar_stack.set_visible_child_name("search")
        self.search_entry.grab_focus()

    def _on_search_typed(self, entry) -> None:
        if self.vault is None:
            self.search_status.set_text("Open a vault first")
            return
        query = entry.get_text().strip()
        self._clear_results()
        if not query:
            recents = [rel for rel in self.store.state.recent_notes if self.vault.has_file(rel)]
            self.search_status.set_text("Recent notes" if recents else "")
            for rel in recents:
                self._add_result(rel, "")
            return
        hits = search_filenames(self.vault, query)
        self.search_status.set_text(
            f"{len(hits)} filename matches — press Enter for full-text search"
            if hits
            else "No filename matches — press Enter for full-text search"
        )
        for hit in hits[:50]:
            self._add_result(hit.path, "")

    def _on_search_submitted(self, entry) -> None:
        if self.vault is None:
            return
        query = entry.get_text().strip()
        if not query:
            return
        if self.search_index is None or not self.search_index.ready:
            self.search_status.set_text("Still indexing — try again shortly")
            return
        if parse_query(query).tags and (self.graph is None or not self.graph.ready):
            self.search_status.set_text("The tag index is still building — try again shortly")
            return
        self._clear_results()
        note_tags = self.graph.note_tags if self.graph is not None else None
        hits = self.search_index.search_content(query, note_tags)
        if not hits:
            self.search_status.set_text(f"No matches for “{query}”")
            return
        self.search_status.set_text(f"{len(hits)} notes match")
        for hit in hits:
            self._add_result(hit.path, hit.snippet)

    def _clear_results(self) -> None:
        while (row := self.search_results.get_first_child()) is not None:
            self.search_results.remove(row)

    def _add_result(self, path: str, snippet: str) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        title = Gtk.Label(label=name, xalign=0.0, ellipsize=3)
        box.append(title)
        path_label = Gtk.Label(label=path, xalign=0.0, ellipsize=2)
        path_label.add_css_class("dim-label")
        path_label.add_css_class("caption")
        box.append(path_label)
        if snippet:
            snippet_label = Gtk.Label(label=snippet, xalign=0.0, wrap=True, lines=2, ellipsize=3)
            snippet_label.add_css_class("caption")
            box.append(snippet_label)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        row = Gtk.ListBoxRow(child=box)
        row.note_path = path
        self.search_results.append(row)

    def _on_search_row(self, _list, row) -> None:
        words = parse_query(self.search_entry.get_text()).words
        self._pending_highlight = words[0] if words else ""
        self.reader.load_note(row.note_path)

    # -- find in note ------------------------------------------------------

    def _show_find(self) -> None:
        self.find_bar.set_search_mode(True)
        self.find_entry.grab_focus()

    def _find_controller(self):
        return self.reader.webview.get_find_controller()

    def _on_find_changed(self, entry) -> None:
        text = entry.get_text()
        controller = self._find_controller()
        if not text:
            controller.search_finish()
            return
        options = WebKit.FindOptions.CASE_INSENSITIVE | WebKit.FindOptions.WRAP_AROUND
        controller.search(text, options, 500)

    def _on_find_next(self, _entry) -> None:
        self._find_controller().search_next()

    # -- external handoffs -------------------------------------------------

    def _on_external_uri(self, _reader, uri: str) -> None:
        Gtk.UriLauncher(uri=uri).launch(self, None, None)

    def _on_external_file(self, _reader, rel: str) -> None:
        if self.vault is not None and self.vault.has_file(rel):
            self._launch_file(self.vault.root / rel)

    def _launch_file(self, path: Path) -> None:
        Gtk.FileLauncher(file=Gio.File.new_for_path(str(path))).launch(self, None, None)

    def _on_ambiguous(self, _reader, target: str, _source: str) -> None:
        if self.vault is None:
            return
        candidates = sorted(self.vault.notes_named(target.rsplit("/", 1)[-1]))
        if not candidates:
            self._toast(f"No note named {target}")
            return
        dialog = Adw.AlertDialog(
            heading=f"“{target}” matches {len(candidates)} notes",
            body="Choose the one to open.",
        )
        dialog.add_response("cancel", "Cancel")
        for index, candidate in enumerate(candidates[:MAX_AMBIGUOUS_CHOICES]):
            dialog.add_response(str(index), candidate)
        dialog.set_default_response("cancel")

        def on_response(_dialog, response):
            if response.isdigit():
                self.reader.load_note(candidates[int(response)])

        dialog.connect("response", on_response)
        dialog.present(self)

    def _on_page_action(self, _reader, action: str, argument: str) -> None:
        if action == "open-vault":
            self._open_vault_dialog()
        elif action == "open-file":
            self._open_file_dialog()
        elif action == "open-recent":
            path = Path(unquote(argument))
            if path.is_dir():
                self._open_vault(path)
            else:
                self._toast(f"Vault no longer exists: {path}")

    def _on_hover_link(self, _reader, uri: str) -> None:
        self._cancel_preview()
        if not uri:
            self.hover_label.set_visible(False)
            return
        parsed = urlparse(uri)
        if parsed.scheme == "reader":
            segments = [unquote(part) for part in parsed.path.split("/") if part]
            text = "/".join(segments[1:]) if len(segments) > 1 else uri
            if len(segments) > 1 and segments[0] == "note":
                rel = "/".join(segments[1:])
                if rel and rel != self.current_note:
                    self._preview_pending = rel
                    self._preview_timeout = GLib.timeout_add(
                        HOVER_PREVIEW_DELAY_MS, self._show_preview
                    )
        else:
            text = uri
        self.hover_label.set_text(text)
        self.hover_label.set_visible(True)

    # -- hover preview -----------------------------------------------------

    def _on_pointer_motion(self, _controller, x: float, y: float) -> None:
        self._pointer = (x, y)

    def _ensure_preview(self) -> None:
        if self._preview_reader is not None:
            return
        self._preview_reader = ReaderView(share_from=self._first_reader)
        webview = self._preview_reader.webview
        # The preview is display-only: with input off, a click lands on the page
        # behind it and can never navigate the popover's own surface.
        webview.set_sensitive(False)
        webview.set_size_request(420, 320)
        self.preview_popover = Gtk.Popover(autohide=False, child=webview)
        self.preview_popover.set_parent(self.content_overlay)

    def _cancel_preview(self) -> None:
        self._preview_pending = ""
        if self._preview_timeout:
            GLib.source_remove(self._preview_timeout)
            self._preview_timeout = 0
        if self._preview_reader is not None and self.preview_popover.get_visible():
            self.preview_popover.popdown()

    def _show_preview(self) -> bool:
        from gi.repository import Gdk

        self._preview_timeout = 0
        rel = self._preview_pending
        if not rel or self.renderer is None:
            return False
        self._ensure_preview()
        rect = Gdk.Rectangle()
        rect.x, rect.y = int(self._pointer[0]), int(self._pointer[1])
        rect.width = rect.height = 1
        self.preview_popover.set_pointing_to(rect)
        uri = f"reader:///preview/{GLib.uri_escape_string(rel, '/', True)}"
        self._preview_reader.webview.load_uri(uri)
        self.preview_popover.popup()
        return False

    # -- file monitoring ---------------------------------------------------

    def _watch_current_note(self, path: Path | None) -> None:
        if self.monitor is not None:
            self.monitor.cancel()
            self.monitor = None
        if path is None:
            return
        gfile = Gio.File.new_for_path(str(path))
        self.monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.monitor.connect("changed", self._on_note_changed)

    def _on_note_changed(self, _monitor, _file, _other, event) -> None:
        if event not in (
            Gio.FileMonitorEvent.CHANGES_DONE_HINT,
            Gio.FileMonitorEvent.DELETED,
            Gio.FileMonitorEvent.RENAMED,
        ):
            return
        toast = Adw.Toast(title="This note changed on disk", button_label="Reload")
        toast.connect("button-clicked", lambda *_: self._reload())
        self.toasts.add_toast(toast)

    # -- toggles and preferences -------------------------------------------

    def _on_toggle_source(self, action, value) -> None:
        action.set_state(value)
        self.source_view = value.get_boolean()
        self._reload_all_tabs()

    def _on_show_hidden(self, action, value) -> None:
        action.set_state(value)
        self.store.state.show_hidden = value.get_boolean()
        self.tree.show_hidden = self.store.state.show_hidden
        self.tree.refresh()

    def _on_markdown_only(self, action, value) -> None:
        action.set_state(value)
        self.store.state.markdown_only = value.get_boolean()
        self.tree.markdown_only = self.store.state.markdown_only
        self.tree.refresh()

    def _on_restore_session(self, action, value) -> None:
        action.set_state(value)
        self.store.state.restore_session = value.get_boolean()

    def _on_appearance(self, action, value) -> None:
        action.set_state(value)
        self.store.state.appearance = value.get_string()
        self._apply_appearance(self.store.state.appearance)
        self._reload_all_tabs()

    def _reload_all_tabs(self) -> None:
        for reader in self._readers.values():
            reader.webview.reload()

    def _apply_appearance(self, appearance: str) -> None:
        manager = Adw.StyleManager.get_default()
        scheme = {
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
        }.get(appearance, Adw.ColorScheme.DEFAULT)
        manager.set_color_scheme(scheme)

    def _toggle_sidebar(self) -> None:
        self.sidebar_widget.set_visible(not self.sidebar_widget.get_visible())

    def _new_tab(self) -> None:
        reader = self._create_tab()
        if self.current_note:
            reader.load_note(self.current_note)
        else:
            reader.load_page("welcome")

    def _close_current_tab(self) -> None:
        page = self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _on_zen(self, action, value) -> None:
        action.set_state(value)
        self._set_zen(value.get_boolean())

    def _set_zen(self, on: bool) -> None:
        """Enters or leaves reading mode: no chrome, no sidebar, just the note."""
        if on == getattr(self, "_zen", False):
            return
        self._zen = on
        zen_action = self.lookup_action("zen")
        if zen_action is not None and zen_action.get_state().get_boolean() != on:
            zen_action.set_state(GLib.Variant.new_boolean(on))
        self.leave_zen_action.set_enabled(on)
        if on:
            self._pre_zen_sidebar = self.sidebar_widget.get_visible()
            self.sidebar_widget.set_visible(False)
            self.tab_bar.set_visible(False)
            self.toolbar_view.set_reveal_top_bars(False)
            self.fullscreen()
            self._toast("Reading mode — press Esc or F11 to leave")
        else:
            self.unfullscreen()
            self.toolbar_view.set_reveal_top_bars(True)
            self.tab_bar.set_visible(True)
            self.sidebar_widget.set_visible(getattr(self, "_pre_zen_sidebar", True))

    def _export_pdf_dialog(self) -> None:
        if not self.current_note:
            self._toast("Open a note first")
            return
        stem = self.current_note.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        dialog = Gtk.FileDialog(title="Export as PDF", initial_name=f"{stem}.pdf")
        dialog.save(self, None, self._export_target_chosen)

    def _export_target_chosen(self, dialog, result) -> None:
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        if gfile is not None:
            self._export_pdf_to(gfile)

    def _export_pdf_to(self, gfile) -> None:
        """Prints the current page to a PDF outside the vault; inside it is refused."""
        path = Path(gfile.get_path())
        if self.vault is not None and self.vault.contains(path):
            self._toast("Refusing to write inside the vault — choose a folder outside it")
            return
        operation = WebKit.PrintOperation.new(self.reader.webview)
        settings = Gtk.PrintSettings()
        settings.set(Gtk.PRINT_SETTINGS_OUTPUT_URI, gfile.get_uri())
        settings.set(Gtk.PRINT_SETTINGS_OUTPUT_FILE_FORMAT, "pdf")
        # Without the file backend named, GTK routes to the default printer instead.
        settings.set_printer("Print to File")
        operation.set_print_settings(settings)
        outcome = {"failed": False}

        def on_failed(_operation, error):
            outcome["failed"] = True
            self._toast(f"PDF export failed: {error.message}")

        def on_finished(_operation):
            if not outcome["failed"]:
                self._toast(f"Exported {path.name}")

        operation.connect("failed", on_failed)
        operation.connect("finished", on_finished)
        operation.print_()

    def _zoom(self, delta: float | None) -> None:
        zoom = 1.0 if delta is None else max(0.5, min(3.0, self.store.state.zoom + delta))
        self.store.state.zoom = round(zoom, 2)
        for reader in self._readers.values():
            reader.webview.set_zoom_level(self.store.state.zoom)

    # -- current-note utilities --------------------------------------------

    def _reveal_current(self) -> None:
        if self.vault is not None and self.current_note:
            gfile = Gio.File.new_for_path(str(self.vault.root / self.current_note))
            Gtk.FileLauncher(file=gfile).open_containing_folder(self, None, None)

    def _open_current_externally(self) -> None:
        if self.vault is not None and self.current_note:
            self._launch_file(self.vault.root / self.current_note)

    def _copy_current(self, what: str) -> None:
        if self.vault is None or not self.current_note:
            return
        if what == "source":
            text = self.vault.read_note(self.current_note).text
        elif what == "wikilink":
            stem = self.current_note.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            text = f"[[{stem}]]"
        else:
            text = self.current_note
        self.get_clipboard().set(text)
        self._toast("Copied")

    # -- dialogs -----------------------------------------------------------

    def _show_shortcuts(self) -> None:
        grid = Gtk.Grid(row_spacing=8, column_spacing=24, margin_top=16, margin_bottom=16)
        grid.set_margin_start(24)
        grid.set_margin_end(24)
        for row, (keys, description) in enumerate(SHORTCUTS):
            key_label = Gtk.Label(label=keys, xalign=1.0)
            key_label.add_css_class("dim-label")
            grid.attach(key_label, 0, row, 1, 1)
            grid.attach(Gtk.Label(label=description, xalign=0.0), 1, row, 1, 1)
        dialog = Adw.Dialog(title="Keyboard Shortcuts", content_width=460)
        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        view.set_content(Gtk.ScrolledWindow(child=grid, propagate_natural_height=True))
        dialog.set_child(view)
        dialog.present(self)

    def _show_about(self) -> None:
        about = Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon=APP_ID,
            version=__version__,
            developer_name="Luis Tineo",
            license_type=Gtk.License.MIT_X11,
            comments=(
                "A read-only reader for Obsidian vaults. Opens notes in place, "
                "executes nothing, and never writes into the vault."
            ),
        )
        about.present(self)

    def _toast(self, message: str) -> None:
        self.toasts.add_toast(Adw.Toast(title=message))

    # -- persistence -------------------------------------------------------

    def _refresh_recents_menu(self) -> None:
        self.recents_section.remove_all()
        for root in self.store.state.recent_vaults[:5]:
            item = Gio.MenuItem.new(Path(root).name, None)
            item.set_action_and_target_value(
                "win.open-recent-vault", GLib.Variant.new_string(root)
            )
            self.recents_section.append_item(item)
        if not self.lookup_action("open-recent-vault"):
            action = Gio.SimpleAction.new("open-recent-vault", GLib.VariantType.new("s"))

            def open_recent(_action, value):
                self._on_page_action(None, "open-recent", value.get_string())

            action.connect("activate", open_recent)
            self.add_action(action)

    def _on_close(self, _window) -> bool:
        if self.vault_monitor is not None:
            self.vault_monitor.cancel()
        if self.index_store is not None:
            self.index_store.close()
        state = self.store.state
        state.window_width = self.get_width()
        state.window_height = self.get_height()
        state.sidebar_visible = self.sidebar_widget.get_visible()
        state.sidebar_width = self.paned.get_position()
        state.open_tabs = [
            reader.current_note
            for reader in (
                self._readers.get(self.tab_view.get_nth_page(i).get_child())
                for i in range(self.tab_view.get_n_pages())
            )
            if reader is not None and reader.current_note
        ]
        self.store.save()
        return False
