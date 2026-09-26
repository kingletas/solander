"""The lazy vault file tree: directories expand on demand, dotfiles stay hidden."""

import os
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GObject, Gtk

from ..core.listdiff import splices
from ..core.treeorder import Entry, tree_order
from ..core.vault import NOTE_EXTENSIONS


class TreeNode(GObject.Object):
    """One row of the vault tree: a directory or a file, addressed vault-relatively."""

    def __init__(self, root: Path, rel: str, is_dir: bool):
        super().__init__()
        self.root = root
        self.rel = rel
        self.is_dir = is_dir

    @property
    def name(self) -> str:
        return self.rel.rsplit("/", 1)[-1] or str(self.root)

    @property
    def is_note(self) -> bool:
        return not self.is_dir and self.rel.casefold().endswith(NOTE_EXTENSIONS)


class VaultTree:
    """Builds the ListView over a TreeListModel and reports row activation."""

    def __init__(self, on_activate, on_open_new_tab=None, on_folder_menu=None):
        self.root: Path | None = None
        self.show_hidden = False
        self.markdown_only = True
        self.sort = "name"
        self.hidden_folders: set[str] = set()
        self._on_activate = on_activate
        self._on_open_new_tab = on_open_new_tab
        self._on_folder_menu = on_folder_menu
        self._root_store = Gio.ListStore(item_type=TreeNode)
        # Every directory listing the tree has built, by vault-relative path, for refresh to reach.
        self._stores: dict[str, Gio.ListStore] = {"": self._root_store}
        tree_model = Gtk.TreeListModel.new(
            self._root_store, passthrough=False, autoexpand=False, create_func=self._children
        )
        self.selection = Gtk.SingleSelection(model=tree_model, autoselect=False, can_unselect=True)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup_row)
        factory.connect("bind", self._bind_row)
        self.view = Gtk.ListView(model=self.selection, factory=factory)
        self.view.add_css_class("navigation-sidebar")
        self.view.set_single_click_activate(True)
        # One Tab stop for the whole tree, with the arrow keys inside it, rather than
        # one per row: a folder of a hundred notes was a hundred presses to get past.
        self.view.set_tab_behavior(Gtk.ListTabBehavior.ITEM)
        self.view.connect("activate", self._activated)

    def set_vault(self, root: Path | None) -> None:
        """Points the tree at a vault root, or clears it, starting from a collapsed tree."""
        self.root = root
        self._root_store.remove_all()
        self._stores = {"": self._root_store}
        self.refresh()

    def refresh(self) -> None:
        """Brings every listed directory up to date in place, so expanded folders stay expanded."""
        if self.root is None:
            self._root_store.remove_all()
            return
        for rel, store in list(self._stores.items()):
            if rel and not (self.root / rel).is_dir():
                del self._stores[rel]
                continue
            self._sync(store, self._list_directory(rel))

    @staticmethod
    def _sync(store: Gio.ListStore, nodes: list[TreeNode]) -> None:
        """Edits the store into the given listing, touching only the rows that differ."""
        items = [store.get_item(i) for i in range(store.get_n_items())]
        old = [(item.rel, item.is_dir) for item in items]
        new = [(node.rel, node.is_dir) for node in nodes]
        for position, removed, start, end in splices(old, new):
            store.splice(position, removed, nodes[start:end])

    def _list_directory(self, rel: str) -> list[TreeNode]:
        directory = self.root / rel if rel else self.root
        listed: list[Entry] = []
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return []
        for entry in entries:
            if not self.show_hidden and entry.name.startswith("."):
                continue
            child_rel = f"{rel}/{entry.name}" if rel else entry.name
            if entry.is_dir(follow_symlinks=False):
                if child_rel in self.hidden_folders:
                    continue
                listed.append(Entry(entry.name, True))
            elif entry.is_file(follow_symlinks=False):
                name = entry.name.casefold()
                readable = name.endswith(NOTE_EXTENSIONS) or name.endswith((".canvas", ".base"))
                if self.markdown_only and not readable:
                    continue
                listed.append(Entry(entry.name, False, self._mtime(entry)))
        return [
            TreeNode(self.root, f"{rel}/{item.name}" if rel else item.name, item.is_dir)
            for item in tree_order(listed, self.sort)
        ]

    def _mtime(self, entry) -> float:
        """A file's modified time, read only when the tree is sorted by it."""
        if self.sort != "modified":
            return 0.0
        try:
            return entry.stat(follow_symlinks=False).st_mtime
        except OSError:
            return 0.0

    def _children(self, node: TreeNode):
        if not node.is_dir:
            return None
        store = Gio.ListStore(item_type=TreeNode)
        for child in self._list_directory(node.rel):
            store.append(child)
        self._stores[node.rel] = store
        return store

    def _setup_row(self, _factory, item) -> None:
        expander = Gtk.TreeExpander()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        icon = Gtk.Image()
        label = Gtk.Label(xalign=0.0, ellipsize=3)
        box.append(icon)
        box.append(label)
        expander.set_child(box)
        item.set_child(expander)

        def open_new_tab_from(gesture) -> bool:
            row = item.get_item()
            node = row.get_item() if row is not None else None
            if node is not None and node.is_note and self._on_open_new_tab is not None:
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)
                self._on_open_new_tab(node)
                return True
            return False

        middle = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle.connect("pressed", lambda gesture, *_: open_new_tab_from(gesture))
        expander.add_controller(middle)

        primary = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)

        def primary_pressed(gesture, *_):
            state = gesture.get_current_event_state()
            if state & Gdk.ModifierType.CONTROL_MASK:
                open_new_tab_from(gesture)

        primary.connect("pressed", primary_pressed)
        expander.add_controller(primary)

        secondary = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)

        def secondary_pressed(gesture, *_):
            row = item.get_item()
            node = row.get_item() if row is not None else None
            if node is not None and node.is_dir and self._on_folder_menu is not None:
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)
                self._on_folder_menu(node, expander)

        secondary.connect("pressed", secondary_pressed)
        expander.add_controller(secondary)

    def _bind_row(self, _factory, item) -> None:
        row = item.get_item()
        node = row.get_item()
        expander = item.get_child()
        expander.set_list_row(row)
        box = expander.get_child()
        icon = box.get_first_child()
        label = icon.get_next_sibling()
        icon.set_from_icon_name("folder-symbolic" if node.is_dir else "text-x-generic-symbolic")
        name = node.name
        if node.is_note:
            name = name.rsplit(".", 1)[0]
        label.set_text(name)
        label.set_tooltip_text(node.rel)
        item.set_accessible_label(name)

    def _activated(self, _view, position: int) -> None:
        row = self.selection.get_model().get_item(position)
        if row is None:
            return
        node = row.get_item()
        if node.is_dir:
            row.set_expanded(not row.get_expanded())
        else:
            self._on_activate(node)

    def select_path(self, rel: str) -> None:
        """Highlights the row for a note when it is visible in the expanded tree."""
        model = self.selection.get_model()
        for position in range(model.get_n_items()):
            row = model.get_item(position)
            node = row.get_item()
            if node is not None and node.rel == rel:
                self.selection.set_selected(position)
                return

    def reveal(self, rel: str) -> None:
        """Expands every ancestor of a path, then selects and scrolls to its row."""
        parts = rel.split("/")
        for depth in range(1, len(parts) + 1):
            target = "/".join(parts[:depth])
            model = self.selection.get_model()
            for position in range(model.get_n_items()):
                row = model.get_item(position)
                node = row.get_item()
                if node is None or node.rel != target:
                    continue
                if node.is_dir:
                    row.set_expanded(True)
                if target == rel:
                    self.selection.set_selected(position)
                    self.view.scroll_to(position, Gtk.ListScrollFlags.NONE, None)
                break
