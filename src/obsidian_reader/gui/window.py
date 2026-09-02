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
from ..core.csssnippets import load_snippets
from ..core.graph import VaultGraph, local_neighbors
from ..core.indexing import sync_indexes
from ..core.render import NoteRenderer, build_message_page, build_page, build_source_page
from ..core.resolver import resolve_note
from ..core.search import VaultSearch, parse_query, search_filenames
from ..core.session import SessionStore
from ..core.store import open_index_store
from ..core.vault import Vault, file_kind, hidden_under
from .filetree import VaultTree
from .localgraph import LocalGraphView
from .monitor import VaultMonitor
from .pdfview import PdfWindow, poppler_available
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
    ("F8", "Toggle the outline panel"),
    ("F9", "Toggle sidebar"),
    ("F11", "Reading mode (Esc leaves)"),
    ("Ctrl+M", "View the note as a mind map"),
    ("Right-click a folder", "Hide it (View menu unhides)"),
    ("Ctrl+Shift+E", "Export as PDF"),
    ("Ctrl++ / Ctrl+- / Ctrl+0", "Zoom in / out / reset"),
    ("F1", "User guide"),
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
        self._snippets_css = ""
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
        self.sidebar_toggle = Gtk.ToggleButton(
            icon_name="sidebar-show-symbolic", active=self.store.state.sidebar_visible
        )
        self.sidebar_toggle.set_tooltip_text("Sidebar (F9)")
        self.sidebar_toggle.connect(
            "toggled", lambda button: self.sidebar_widget.set_visible(button.get_active())
        )
        header.pack_start(self.sidebar_toggle)
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

        header.pack_end(self._main_menu_button())
        self.outline_toggle = Gtk.ToggleButton(
            icon_name="view-list-symbolic", active=self.store.state.outline_visible
        )
        self.outline_toggle.set_tooltip_text("Outline (F8)")
        self.outline_toggle.connect(
            "toggled", lambda button: self._set_outline_visible(button.get_active())
        )
        header.pack_end(self.outline_toggle)
        search_button = Gtk.Button(icon_name="system-search-symbolic")
        search_button.set_tooltip_text("Search the vault (Ctrl+Shift+F)")
        search_button.connect("clicked", lambda *_: self._show_search())
        header.pack_end(search_button)
        header.pack_end(self._readonly_badge())

        self.sidebar_widget = self._build_sidebar()
        self.sidebar_widget.set_visible(self.store.state.sidebar_visible)

        # The rail runs the full window height beside a content pane that owns
        # the header bar — two surfaces, not one tinted sheet.
        self.toolbar_view = Adw.ToolbarView()
        self.toolbar_view.add_top_bar(header)
        self.toolbar_view.set_content(self._build_reading_area())

        self.paned = Gtk.Paned(
            orientation=Gtk.Orientation.HORIZONTAL,
            position=self.store.state.sidebar_width,
            shrink_start_child=False,
            resize_start_child=False,
        )
        self.paned.set_start_child(self.sidebar_widget)
        self.paned.set_end_child(self.toolbar_view)
        self.toasts = Adw.ToastOverlay(child=self.paned)
        self.set_content(self.toasts)
        self.connect("close-request", self._on_close)
        self._install_drop_target()
        self._load_css()
        self._refresh_recents_menu()
        self.sidebar_stack.connect("notify::visible-child", self._on_sidebar_page_changed)
        if self.store.state.outline_visible and self.store.state.outline_side == "left":
            self.sidebar_stack.set_visible_child_name("outline")
        self._sync_outline_toggle()
        self._create_tab()

    def _build_sidebar(self) -> Gtk.Widget:
        self._install_bundled_icons()
        self.sidebar_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)

        self.tree = VaultTree(
            self._on_tree_activate, self._on_tree_open_new_tab, self._on_hide_folder
        )
        self.tree.show_hidden = self.store.state.show_hidden
        self.tree.markdown_only = self.store.state.markdown_only
        files_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.quick_heading = Gtk.Label(label="PINNED & RECENT", xalign=0.0)
        self.quick_heading.add_css_class("quick-heading")
        self.quick_list = Gtk.ListBox()
        self.quick_list.add_css_class("navigation-sidebar")
        self.quick_list.connect("row-activated", self._on_panel_row)
        self.quick_expander = Gtk.Expander(
            expanded=self.store.state.quick_expanded, visible=False
        )
        self.quick_expander.set_label_widget(self.quick_heading)
        self.quick_expander.set_child(self.quick_list)
        self.quick_expander.connect("notify::expanded", self._on_quick_expanded)
        files_box.append(self.quick_expander)
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(6)
        separator.add_css_class("rail-separator")
        files_box.append(separator)
        folders_heading = Gtk.Label(label="FOLDERS", xalign=0.0)
        folders_heading.add_css_class("quick-heading")
        files_box.append(folders_heading)
        files_box.append(Gtk.ScrolledWindow(child=self.tree.view, vexpand=True))
        self._add_sidebar_page(files_box, "files", "Files", "folder-symbolic")

        search_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        search_box.set_margin_top(6)
        self.search_entry = Gtk.SearchEntry(
            placeholder_text="Search notes (Ctrl+P) — path:, file:, tag:"
        )
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

        self.rail_outline_list = Gtk.ListBox()
        self.rail_outline_list.add_css_class("navigation-sidebar")
        self.rail_outline_list.add_css_class("rail-outline")
        self.rail_outline_list.connect("row-activated", self._on_outline_row)
        outline_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outline_heading = Gtk.Label(label="OUTLINE", xalign=0.0)
        outline_heading.add_css_class("quick-heading")
        outline_box.append(outline_heading)
        outline_box.append(Gtk.ScrolledWindow(child=self.rail_outline_list, vexpand=True))
        self._add_sidebar_page(outline_box, "outline", "Outline", "view-list-symbolic")

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
        self._add_sidebar_page(tags_box, "tags", "Tags", "tag-symbolic")

        self.bookmarks_list = Gtk.ListBox()
        self.bookmarks_list.add_css_class("navigation-sidebar")
        self.bookmarks_list.connect("row-activated", self._on_panel_row)
        bookmarks_scroll = Gtk.ScrolledWindow(child=self.bookmarks_list, vexpand=True)
        self._add_sidebar_page(
            bookmarks_scroll, "bookmarks", "Bookmarks", "user-bookmarks-symbolic"
        )

        self.local_graph = LocalGraphView(lambda rel: self.reader.load_note(rel))
        self._add_sidebar_page(
            self.local_graph.area, "graph", "Graph", "network-workgroup-symbolic"
        )

        switcher = Gtk.StackSwitcher(stack=self.sidebar_stack)
        switcher.set_halign(Gtk.Align.CENTER)

        self.rail_title = Gtk.Label(label=APP_NAME.upper(), xalign=0.5, ellipsize=3)
        self.rail_title.add_css_class("rail-title")
        head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        head.set_margin_top(12)
        head.set_margin_bottom(6)
        head.set_margin_start(10)
        head.set_margin_end(10)
        head.append(self.rail_title)
        head.append(switcher)
        # The rail has no header bar, so its top strip still drags the window.
        handle = Gtk.WindowHandle(child=head)

        self.index_status = Gtk.Label(xalign=0.0)
        self.index_status.add_css_class("dim-label")
        self.index_status.set_margin_start(12)
        self.index_status.set_margin_top(6)
        self.index_status.set_margin_bottom(8)

        rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        rail.add_css_class("atelier-rail")
        rail.append(handle)
        rail.append(self.sidebar_stack)
        rail.append(self.index_status)
        return rail

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

    def _pinned_notes(self) -> list[str]:
        if self.vault is None:
            return []
        return self.store.state.pinned_notes.get(str(self.vault.root), [])

    def _toggle_pin(self) -> None:
        """Pins or unpins the current note in the sidebar's Pinned & recent section."""
        if self.vault is None or not self.current_note:
            self._toast("Open a note first")
            return
        key = str(self.vault.root)
        pinned = self.store.state.pinned_notes.setdefault(key, [])
        if self.current_note in pinned:
            pinned.remove(self.current_note)
            self._toast("Unpinned from the sidebar")
        else:
            pinned.append(self.current_note)
            self._toast("Pinned to the sidebar")
        self._refresh_quick_list()

    def _on_quick_expanded(self, expander, _param) -> None:
        self.store.state.quick_expanded = expander.get_expanded()

    def _refresh_quick_list(self) -> None:
        """Rebuilds the Pinned & recent section: pins first, then the latest notes."""
        self._clear_list(self.quick_list)
        if self.vault is None:
            self.quick_expander.set_visible(False)
            return
        hidden = self._hidden_folders()
        pinned = [
            rel for rel in self._pinned_notes()
            if self.vault.has_file(rel) and not hidden_under(rel, hidden)
        ]
        recents = [
            rel for rel in self.store.state.recent_notes
            if rel not in pinned and self.vault.has_file(rel) and not hidden_under(rel, hidden)
        ][:5]
        for rel, icon in [(r, "view-pin-symbolic") for r in pinned] + [
            (r, "document-open-recent-symbolic") for r in recents
        ]:
            box = Gtk.Box(spacing=6)
            box.append(Gtk.Image(icon_name=icon))
            name = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            label = Gtk.Label(label=name, xalign=0.0, ellipsize=3)
            box.append(label)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            row = Gtk.ListBoxRow(child=box)
            row.note_path = rel
            row.set_tooltip_text(rel)
            self.quick_list.append(row)
        self.quick_expander.set_visible(bool(pinned or recents))

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
        context = Gio.Menu()
        context.append("Title & Breadcrumb", "win.show-breadcrumb")
        context.append("Metadata Line", "win.show-note-meta")
        context.append("Linked Mentions", "win.show-backlinks")
        outline_side = Gio.Menu()
        outline_side.append("Left Sidebar", "win.outline-side::left")
        outline_side.append("Right Panel", "win.outline-side::right")
        view = Gio.Menu()
        view.append("New Tab", "win.new-tab")
        view.append("Reading Mode", "win.zen")
        view.append("Raw Source View", "win.toggle-source")
        view.append_submenu("Note Context", context)
        view.append_submenu("Outline Position", outline_side)
        view.append("Show Hidden Files", "win.show-hidden")
        view.append("Markdown Files Only", "win.markdown-only")
        view.append("Vault CSS Snippets", "win.css-snippets")
        view.append("Unhide All Folders", "win.unhide-folders")
        view.append("Restore Session on Launch", "win.restore-session")
        menu.append_section(None, view)
        note = Gio.Menu()
        note.append("Pin / Unpin Note", "win.pin-note")
        note.append("View as Mind Map", "win.mindmap")
        note.append("Export as PDF…", "win.export-pdf")
        note.append("Reveal in Files", "win.reveal")
        note.append("Open Externally", "win.open-external")
        note.append("Copy Markdown Source", "win.copy-source")
        note.append("Copy Vault Path", "win.copy-path")
        note.append("Copy as Wikilink", "win.copy-wikilink")
        menu.append_section(None, note)
        meta = Gio.Menu()
        meta.append("Clear Index Cache", "win.clear-cache")
        meta.append("Getting Started", "win.getting-started")
        meta.append("User Guide", "win.user-guide")
        meta.append("Keyboard Shortcuts", "win.shortcuts")
        meta.append(f"About {APP_NAME}", "win.about")
        menu.append_section(None, meta)
        button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        button.set_tooltip_text("Main menu")
        return button

    def _readonly_badge(self) -> Gtk.MenuButton:
        """The read-only state as a quiet lock: the reason and next actions one click away."""
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        heading = Gtk.Label(label="Read-only, by design", xalign=0.0)
        heading.add_css_class("heading")
        content.append(heading)
        explanation = Gtk.Label(
            label=(
                "This app reads your vault in place and never writes into it. "
                "To change a note, open it in Obsidian or any editor; edits "
                "show up here within seconds."
            ),
            wrap=True,
            xalign=0.0,
            max_width_chars=42,
        )
        content.append(explanation)
        for label, action in (
            ("View Raw Source", "win.toggle-source"),
            ("Open in Default Editor", "win.open-external"),
            ("Reveal in Files", "win.reveal"),
        ):
            button = Gtk.Button(label=label, action_name=action)
            button.set_has_frame(False)
            button.get_child().set_xalign(0.0)
            content.append(button)
        badge = Gtk.MenuButton(
            icon_name="changes-prevent-symbolic", popover=Gtk.Popover(child=content)
        )
        badge.add_css_class("flat")
        badge.set_tooltip_text("Read-only — why, and what to do instead")
        return badge

    def _build_reading_area(self) -> Gtk.Widget:
        """The reading pane with the outline as a real, closable panel on its right."""
        state = self.store.state
        restore_right = state.outline_visible and state.outline_side == "right"
        self.outline_split = Adw.OverlaySplitView(
            sidebar_position=Gtk.PackType.END,
            show_sidebar=restore_right,
            min_sidebar_width=200,
            max_sidebar_width=300,
            sidebar_width_fraction=0.22,
        )
        self.outline_split.set_content(self._build_content())
        self.outline_split.set_sidebar(self._build_outline_panel())
        return self.outline_split

    def _build_outline_panel(self) -> Gtk.Widget:
        head = Gtk.Box(spacing=6)
        title = Gtk.Label(label="OUTLINE", xalign=0.0, hexpand=True)
        title.add_css_class("panel-heading")
        close = Gtk.Button(icon_name="window-close-symbolic")
        close.add_css_class("flat")
        close.set_tooltip_text("Hide the outline (F8)")
        close.connect("clicked", lambda *_: self._set_outline_visible(False))
        head.append(title)
        head.append(close)
        head.set_margin_start(12)
        head.set_margin_end(6)
        head.set_margin_top(8)

        self.outline_list = Gtk.ListBox()
        self.outline_list.add_css_class("navigation-sidebar")
        self.outline_list.connect("row-activated", self._on_outline_row)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        panel.add_css_class("outline-panel")
        panel.append(head)
        panel.append(Gtk.ScrolledWindow(child=self.outline_list, vexpand=True))
        return panel

    def _set_outline_visible(self, on: bool) -> None:
        """One switch for the outline, opening it on the chosen side — never both."""
        if on:
            if self.store.state.outline_side == "left":
                self.outline_split.set_show_sidebar(False)
                self.sidebar_toggle.set_active(True)
                self.sidebar_stack.set_visible_child_name("outline")
            else:
                if self.sidebar_stack.get_visible_child_name() == "outline":
                    self.sidebar_stack.set_visible_child_name("files")
                self.outline_split.set_show_sidebar(True)
        else:
            self.outline_split.set_show_sidebar(False)
            if self.sidebar_stack.get_visible_child_name() == "outline":
                self.sidebar_stack.set_visible_child_name("files")
        self.store.state.outline_visible = on
        self._sync_outline_toggle()

    def _outline_shown(self) -> bool:
        on_left = (
            self.sidebar_widget.get_visible()
            and self.sidebar_stack.get_visible_child_name() == "outline"
        )
        return on_left or self.outline_split.get_show_sidebar()

    def _sync_outline_toggle(self) -> None:
        shown = self._outline_shown()
        if self.outline_toggle.get_active() != shown:
            self.outline_toggle.set_active(shown)

    def _on_sidebar_page_changed(self, *_args) -> None:
        """Choosing the rail's Outline page collapses the right panel: one outline."""
        if self.sidebar_stack.get_visible_child_name() == "outline":
            if self.outline_split.get_show_sidebar():
                self.outline_split.set_show_sidebar(False)
        self._sync_outline_toggle()

    def _on_outline_side(self, action, value) -> None:
        action.set_state(value)
        shown = self._outline_shown()
        self.store.state.outline_side = value.get_string()
        if shown:
            self._set_outline_visible(True)
        else:
            self._sync_outline_toggle()

    def _install_drop_target(self) -> None:
        from gi.repository import Gdk

        drop = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop.connect("drop", lambda _t, value, _x, _y: self._open_gfile(value) or True)
        self.add_controller(drop)

    # Two surfaces, one identity: a deep sepia rail beside the parchment canvas,
    # with the header flattened into the canvas rather than a third tint.
    _CHROME_LIGHT = """
    @define-color accent_bg_color #1c4e9c;
    @define-color accent_fg_color #ffffff;
    @define-color accent_color #1c4e9c;
    @define-color window_bg_color #f9f4e7;
    @define-color window_fg_color #2b2620;
    @define-color headerbar_bg_color #f9f4e7;
    @define-color headerbar_fg_color #2b2620;
    @define-color view_bg_color #f9f4e7;
    @define-color view_fg_color #2b2620;
    @define-color popover_bg_color #f6f0df;
    @define-color popover_fg_color #2b2620;
    @define-color dialog_bg_color #f6f0df;
    @define-color dialog_fg_color #2b2620;
    @define-color card_bg_color #f4eeda;
    @define-color card_fg_color #2b2620;
    @define-color rail_bg #2a2420;
    @define-color rail_fg #d8d0c0;
    @define-color rail_muted #97907f;
    @define-color rail_accent #d0a44e;
    @define-color canvas_muted #6f6455;
    """

    _CHROME_DARK = """
    @define-color accent_bg_color #5c84c4;
    @define-color accent_fg_color #ffffff;
    @define-color accent_color #8fb0e8;
    @define-color window_bg_color #1c1a16;
    @define-color window_fg_color #d9d2c2;
    @define-color headerbar_bg_color #1c1a16;
    @define-color headerbar_fg_color #d9d2c2;
    @define-color view_bg_color #1c1a16;
    @define-color view_fg_color #d9d2c2;
    @define-color popover_bg_color #2a261e;
    @define-color popover_fg_color #d9d2c2;
    @define-color dialog_bg_color #2a261e;
    @define-color dialog_fg_color #d9d2c2;
    @define-color card_bg_color #262218;
    @define-color card_fg_color #d9d2c2;
    @define-color rail_bg #16130f;
    @define-color rail_fg #cfc7b6;
    @define-color rail_muted #857d6d;
    @define-color rail_accent #d0a44e;
    @define-color canvas_muted #a29882;
    """

    _CHROME_STRUCTURE = """
    headerbar windowtitle .title {
        font-family: "Noto Serif", "Liberation Serif", Georgia, serif;
        font-weight: 700;
    }
    headerbar { box-shadow: none; }
    paned > separator { background: alpha(currentColor, 0.12); min-width: 1px; }
    .hover-status { background: alpha(@window_bg_color, 0.9); border-radius: 6px;
                    padding: 2px 8px; margin: 6px; font-size: 0.85em; }
    .navigation-sidebar row:selected {
        box-shadow: inset 3px 0 0 @accent_bg_color;
        background: alpha(@accent_bg_color, 0.12);
        color: @window_fg_color;
    }
    listview.navigation-sidebar > row { padding-top: 3px; padding-bottom: 3px; }
    .quick-heading { font-size: 0.72em; font-weight: bold; letter-spacing: 0.12em;
                     color: alpha(currentColor, 0.55); margin: 10px 12px 2px; }
    .panel-heading { font-size: 0.72em; font-weight: bold; letter-spacing: 0.12em;
                     color: alpha(currentColor, 0.55); }

    /* The rail: one deep surface, gold accents, everything on it made for it. */
    .atelier-rail { background: @rail_bg; color: @rail_fg; }
    .atelier-rail .rail-title {
        font-family: "Noto Serif", "Liberation Serif", Georgia, serif;
        font-size: 0.78em; font-weight: bold; letter-spacing: 0.18em;
        color: @rail_accent;
    }
    .atelier-rail scrolledwindow, .atelier-rail viewport,
    .atelier-rail listview, .atelier-rail list { background: transparent; color: @rail_fg; }
    .atelier-rail row { color: @rail_fg; border-radius: 6px; margin-left: 4px; margin-right: 4px; }
    .atelier-rail row:hover { background: alpha(#ffffff, 0.05); }
    .atelier-rail row:selected {
        background: alpha(@rail_accent, 0.16);
        box-shadow: inset 3px 0 0 @rail_accent;
        color: #f4ecd9;
    }
    .atelier-rail image { color: @rail_muted; }
    .atelier-rail row:selected image { color: @rail_accent; }
    .atelier-rail .dim-label, .atelier-rail .caption { color: @rail_muted; }
    .atelier-rail .quick-heading { color: alpha(@rail_accent, 0.75); }
    .atelier-rail entry {
        background: alpha(#ffffff, 0.07);
        color: @rail_fg;
        border: 1px solid alpha(#ffffff, 0.08);
        caret-color: @rail_fg;
    }
    .atelier-rail entry image { color: @rail_muted; }
    .atelier-rail stackswitcher button { color: @rail_muted; min-width: 30px; }
    .atelier-rail stackswitcher button:hover { color: @rail_fg; }
    .atelier-rail expander { color: @rail_muted; }
    .atelier-rail .rail-separator { background: alpha(#ffffff, 0.08); }
    .atelier-rail .rail-outline row { color: @rail_muted; }
    .atelier-rail .rail-outline row:hover { color: @rail_accent; }
    .atelier-rail .rail-outline .outline-l1 { color: @rail_fg; font-weight: 600; }
    .atelier-rail .rail-outline .outline-l3 { font-size: 0.9em; }
    .atelier-rail stackswitcher button:checked {
        color: @rail_accent;
        background: alpha(@rail_accent, 0.14);
    }

    /* The outline panel dresses in the canvas family: a warm card surface,
       the gold small-caps label, muted serif entries that answer in lapis. */
    .outline-panel { background: @card_bg_color; }
    .outline-panel .panel-heading { color: @rail_accent; letter-spacing: 0.14em; }
    .outline-panel scrolledwindow, .outline-panel viewport,
    .outline-panel list { background: transparent; }
    .outline-panel row {
        border-radius: 6px;
        margin-left: 6px;
        margin-right: 6px;
        color: @canvas_muted;
    }
    .outline-panel row label {
        font-family: "Noto Serif", "Liberation Serif", Georgia, serif;
        font-size: 0.92em;
    }
    .outline-panel row:hover { background: alpha(currentColor, 0.06); color: @accent_color; }
    .outline-panel row:selected {
        background: alpha(@accent_bg_color, 0.12);
        box-shadow: none;
        color: @accent_color;
    }
    .outline-panel button.flat { color: @canvas_muted; }
    .outline-panel .outline-l1 { font-weight: 600; }
    .outline-panel .outline-l3 { font-size: 0.86em; }
    """

    def _load_css(self) -> None:
        from gi.repository import Gdk

        self._chrome_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self._chrome_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        Adw.StyleManager.get_default().connect("notify::dark", self._on_style_flip)
        self._apply_chrome_css()

    def _on_style_flip(self, *_args) -> None:
        """A light/dark flip re-tints the chrome and re-renders every page to match."""
        self._apply_chrome_css()
        self._reload_all_tabs()

    def _apply_chrome_css(self) -> None:
        dark = Adw.StyleManager.get_default().get_dark()
        palette = self._CHROME_DARK if dark else self._CHROME_LIGHT
        self._chrome_provider.load_from_string(palette + self._CHROME_STRUCTURE)

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
        add(
            "toggle-outline",
            lambda *_: self._set_outline_visible(not self.outline_split.get_show_sidebar()),
            ["F8"],
        )
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
        add("mindmap", lambda *_: self._show_mindmap(), ["<Control>m"])
        add("pin-note", lambda *_: self._toggle_pin())
        add("unhide-folders", lambda *_: self._unhide_all_folders())
        add("zoom-in", lambda *_: self._zoom(0.1), ["<Control>plus", "<Control>equal"])
        add("zoom-out", lambda *_: self._zoom(-0.1), ["<Control>minus"])
        add("zoom-reset", lambda *_: self._zoom(None), ["<Control>0"])
        add("clear-cache", lambda *_: self._clear_index_cache())
        add("user-guide", lambda *_: self.reader.load_page("user-guide"), ["F1"])
        add("getting-started", lambda *_: self.reader.load_page("getting-started"))
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
            "css-snippets",
            self._on_css_snippets,
            state=GLib.Variant.new_boolean(self.store.state.css_snippets),
        )
        for name, key in (
            ("show-breadcrumb", "show_breadcrumb"),
            ("show-note-meta", "show_note_meta"),
            ("show-backlinks", "show_backlinks_footer"),
        ):
            add(
                name,
                (lambda a, v, k=key: self._on_context_toggle(a, v, k)),
                state=GLib.Variant.new_boolean(getattr(self.store.state, key)),
            )
        add(
            "appearance",
            self._on_appearance,
            parameter=GLib.VariantType.new("s"),
            state=GLib.Variant.new_string(self.store.state.appearance),
        )
        add(
            "outline-side",
            self._on_outline_side,
            parameter=GLib.VariantType.new("s"),
            state=GLib.Variant.new_string(self.store.state.outline_side),
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
            renderer = NoteRenderer(
                vault, self._typography, lambda: self.graph, lambda: self._snippets_css,
                options=self._page_options,
            )
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
        self.rail_title.set_label(vault.root.name.upper())
        self.tree.hidden_folders = self._hidden_folders()
        self.tree.set_vault(vault.root)
        self._refresh_quick_list()
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
                self._snippets_css = (
                    load_snippets(root) if self.store.state.css_snippets else ""
                )
                renderer = NoteRenderer(
                    vault, self._typography, lambda: self.graph, lambda: self._snippets_css,
                    options=self._page_options,
                )
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
        first_sync = not search.ready
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
        if first_sync:
            # The first render happened before the graph existed, so any
            # dataview blocks showed "index is still building" — render again.
            self._reload_all_tabs()
        return False

    def _hidden_folders(self) -> set[str]:
        """Obsidian's own excluded folders plus the ones hidden in this reader."""
        if self.vault is None:
            return set()
        mine = self.store.state.hidden_folders.get(str(self.vault.root), [])
        return set(self.vault.ignore_filters) | set(mine)

    def _apply_hidden_folders(self) -> None:
        self.tree.hidden_folders = self._hidden_folders()
        self.tree.refresh()
        self._refresh_quick_list()

    def _on_hide_folder(self, node) -> None:
        if self.vault is None:
            return
        key = str(self.vault.root)
        folders = self.store.state.hidden_folders.setdefault(key, [])
        if node.rel in folders:
            return
        folders.append(node.rel)
        self._apply_hidden_folders()
        toast = Adw.Toast(title=f"Hidden {node.rel}", button_label="Unhide")

        def undo(*_args):
            if node.rel in folders:
                folders.remove(node.rel)
            self._apply_hidden_folders()

        toast.connect("button-clicked", undo)
        self.toasts.add_toast(toast)

    def _unhide_all_folders(self) -> None:
        if self.vault is None:
            return
        removed = self.store.state.hidden_folders.pop(str(self.vault.root), [])
        self._apply_hidden_folders()
        obsidian = len(self.vault.ignore_filters)
        message = f"Unhid {len(removed)} folder(s)"
        if obsidian:
            message += f" — {obsidian} stay hidden by Obsidian's own excluded-files setting"
        self._toast(message)

    def _visible_hits(self, hits):
        hidden = self._hidden_folders()
        return [hit for hit in hits if not hidden_under(hit.path, hidden)]

    def _show_mindmap(self) -> None:
        """Toggles between a note and its mind map."""
        uri = self.reader.webview.get_uri() or ""
        if uri.startswith("reader:///mindmap/") and self.current_note:
            self.reader.load_note(self.current_note)
            return
        if not self.current_note or not self.current_note.casefold().endswith((".md", ".markdown")):
            self._toast("Open a note first")
            return
        rel = GLib.uri_escape_string(self.current_note, "/", True)
        self.reader.webview.load_uri(f"reader:///mindmap/{rel}")

    def _typography(self) -> dict:
        """The reading-comfort settings the page shell injects as CSS overrides."""
        state = self.store.state
        return {
            "font": state.reader_font,
            "width": state.line_width,
            "spacing": state.line_spacing,
        }

    def _page_options(self) -> dict:
        """Which note-context elements are switched on under View → Note Context."""
        state = self.store.state
        return {
            "breadcrumb": state.show_breadcrumb,
            "meta": state.show_note_meta,
            "backlinks": state.show_backlinks_footer,
        }

    def _on_context_toggle(self, action, value, key: str) -> None:
        action.set_state(value)
        setattr(self.store.state, key, value.get_boolean())
        self._reload_all_tabs()

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
            if rel.casefold().endswith(".base"):
                if reader is not None:
                    reader.last_render = None
                return self.renderer.render_base_page(rel, theme)
            rendered = self.renderer.render(rel, theme)
            if reader is not None:
                reader.last_render = rendered
            return rendered.page
        if segments and segments[0] == "preview" and self.renderer is not None:
            return self.renderer.render_preview("/".join(segments[1:]), theme)
        if segments and segments[0] == "mindmap" and self.renderer is not None:
            if reader is not None:
                reader.last_render = None
            return self.renderer.render_mindmap("/".join(segments[1:]), theme)
        if segments and segments[0] == "page":
            return self._app_page(segments[1] if len(segments) > 1 else "", theme)
        return ""

    def _docs_dir(self) -> Path | None:
        """The shipped documentation folder: packaged copy first, repo layout second."""
        from importlib import resources

        packaged = resources.files("obsidian_reader").joinpath("docs")
        try:
            if packaged.joinpath("user-guide.md").is_file():
                return Path(str(packaged))
        except (OSError, TypeError):
            pass
        repo_docs = Path(__file__).resolve().parents[3] / "docs"
        return repo_docs if (repo_docs / "user-guide.md").is_file() else None

    def _help_page(self, name: str, theme: str) -> str:
        docs = self._docs_dir()
        if docs is None:
            return build_message_page(
                "Documentation not found",
                "The docs folder is missing from this installation.",
                theme,
            )
        try:
            text = (docs / f"{name}.md").read_text(encoding="utf-8")
        except OSError:
            return build_message_page("Documentation not found", f"No document {name}", theme)
        for target in ("user-guide", "getting-started"):
            text = text.replace(f"({target}.md#", f"(reader:///page/{target}#")
            text = text.replace(f"({target}.md)", f"(reader:///page/{target})")
        renderer = self.renderer or self._fallback_renderer(docs)
        title = "User guide" if name == "user-guide" else "Getting started"
        return renderer.render_text(text, title, theme)

    def _fallback_renderer(self, docs: Path) -> NoteRenderer:
        """A renderer that exists before any vault is open — the docs folder stands in."""
        if getattr(self, "_docs_renderer", None) is None:
            self._docs_renderer = NoteRenderer(Vault.open(docs), self._typography)
        return self._docs_renderer

    def _app_page(self, name: str, theme: str) -> str:
        if name == "welcome":
            return self._welcome_page(theme)
        if name in ("user-guide", "getting-started"):
            return self._help_page(name, theme)
        if name == "empty-vault":
            return build_message_page(
                "This vault has no Markdown notes",
                "The folder opened fine, but there is nothing here to read.",
                theme,
            )
        return build_message_page("Not found", f"No app page named {name}", theme)

    def _welcome_mark(self) -> str:
        """The app mark, inlined so the frontispiece needs no asset request."""
        from importlib import resources

        try:
            svg = resources.files("obsidian_reader.assets").joinpath("icons/mark.svg")
            markup = svg.read_text("utf-8")
        except OSError:
            return ""
        markup = markup.split("?>", 1)[-1].replace(
            'width="128" height="128"', 'width="96" height="96"', 1
        )
        return f'<div class="welcome-mark">{markup}</div>'

    def _welcome_page(self, theme: str) -> str:
        cards = ""
        for root in self.store.state.recent_vaults[:6]:
            name = html.escape(Path(root).name)
            path = html.escape(root)
            href = f"reader:///action/open-recent?arg={quote(root, safe='')}"
            cards += (
                f'<a class="vault-card" href="{href}">'
                f'<span class="vault-card-name">{name}</span>'
                f'<span class="vault-card-path">{path}</span></a>'
            )
        recents_block = ""
        if cards:
            recents_block = (
                '<div class="welcome-recents">'
                '<div class="welcome-recents-title">Recent vaults</div>'
                f"{cards}</div>"
            )
        body = (
            f'<div class="welcome">{self._welcome_mark()}'
            f'<h1 class="welcome-name">{APP_NAME}</h1>'
            '<div class="welcome-tagline">Your vault, read in place</div>'
            '<div class="welcome-rule"></div>'
            '<div class="action-cards">'
            '<a class="action-card" href="reader:///action/open-vault">'
            '<span class="action-card-title">Open a vault</span>'
            '<span class="action-card-hint">A folder of notes, opened read-only</span></a>'
            '<a class="action-card" href="reader:///action/open-file">'
            '<span class="action-card-title">Open a file</span>'
            '<span class="action-card-hint">A single Markdown note</span></a>'
            "</div>"
            '<div class="welcome-docs">New here? '
            '<a href="reader:///page/getting-started">Getting started</a> · '
            '<a href="reader:///page/user-guide">User guide</a></div>'
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
        if parsed.scheme == "reader" and segments and segments[0] in ("note", "mindmap"):
            # A mind map is still "being on" its note: the title, tree selection,
            # and the Ctrl+M toggle all keep working while the map is shown.
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
            self._fill_outline([])
            self.title_widget.set_title(APP_NAME)
            self._watch_current_note(None)
        self._cancel_preview()
        self._update_links_panel()
        self._update_local_graph()
        self._refresh_quick_list()

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
        """The outline shows in two places — the right panel and the rail page."""
        for listbox in (self.outline_list, self.rail_outline_list):
            self._fill_outline_list(listbox, outline)

    def _fill_outline_list(self, listbox, outline) -> None:
        while (row := listbox.get_first_child()) is not None:
            listbox.remove(row)
        for heading in outline:
            label = Gtk.Label(label=heading.text, xalign=0.0, wrap=True)
            label.set_margin_start((heading.level - 1) * 12)
            label.set_margin_top(2)
            label.set_margin_bottom(2)
            label.add_css_class(f"outline-l{min(heading.level, 3)}")
            row = Gtk.ListBoxRow(child=label)
            row.anchor = heading.anchor
            listbox.append(row)
        if not outline:
            placeholder = Gtk.Label(label="No headings in this note", xalign=0.0, wrap=True)
            placeholder.add_css_class("dim-label")
            row = Gtk.ListBoxRow(child=placeholder, activatable=False, selectable=False)
            listbox.append(row)

    def _on_outline_row(self, _list, row) -> None:
        anchor = getattr(row, "anchor", "")
        if self.current_note and anchor:
            self.reader.load_note(self.current_note, anchor)

    def _on_tree_activate(self, node) -> None:
        if node.is_note or file_kind(node.rel) in ("canvas", "base"):
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
            hidden = self._hidden_folders()
            recents = [
                rel
                for rel in self.store.state.recent_notes
                if self.vault.has_file(rel) and not hidden_under(rel, hidden)
            ]
            self.search_status.set_text("Recent notes" if recents else "")
            for rel in recents:
                self._add_result(rel, "")
            return
        hits = self._visible_hits(search_filenames(self.vault, query))
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
        hits = self._visible_hits(self.search_index.search_content(query, note_tags))
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
        if file_kind(path.name) == "pdf" and poppler_available():
            PdfWindow(path, self).present()
            return
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
        elif action == "tag" and argument:
            self.search_entry.set_text(f"tag:{argument}")
            self._show_search()
            self._on_search_submitted(self.search_entry)
        elif action == "reveal-folder" and argument:
            self.sidebar_widget.set_visible(True)
            self.sidebar_stack.set_visible_child_name("files")
            self.tree.reveal(argument)

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

    def _on_css_snippets(self, action, value) -> None:
        action.set_state(value)
        self.store.state.css_snippets = value.get_boolean()
        if self.vault is not None:
            self._snippets_css = (
                load_snippets(self.vault.root) if self.store.state.css_snippets else ""
            )
        self._reload_all_tabs()

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
        self.sidebar_toggle.set_active(not self.sidebar_widget.get_visible())

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
            self._pre_zen_outline = self._outline_shown()
            self.sidebar_widget.set_visible(False)
            self.outline_split.set_show_sidebar(False)
            self.tab_bar.set_visible(False)
            self.toolbar_view.set_reveal_top_bars(False)
            self.fullscreen()
            self._toast("Reading mode — press Esc or F11 to leave")
        else:
            self.unfullscreen()
            self.toolbar_view.set_reveal_top_bars(True)
            self.tab_bar.set_visible(True)
            restored = getattr(self, "_pre_zen_sidebar", True)
            self.sidebar_widget.set_visible(restored)
            self.sidebar_toggle.set_active(restored)
            self._set_outline_visible(getattr(self, "_pre_zen_outline", False))

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
