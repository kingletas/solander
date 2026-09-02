"""The lazy vault file tree: directories expand on demand, dotfiles stay hidden."""

import os
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GObject, Gtk

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

    def __init__(self, on_activate, on_open_new_tab=None):
        self.root: Path | None = None
        self.show_hidden = False
        self.markdown_only = True
        self._on_activate = on_activate
        self._on_open_new_tab = on_open_new_tab
        self._root_store = Gio.ListStore(item_type=TreeNode)
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
        self.view.connect("activate", self._activated)

    def set_vault(self, root: Path | None) -> None:
        """Points the tree at a vault root, or clears it."""
        self.root = root
        self.refresh()

    def refresh(self) -> None:
        """Relists the root level; expanded rows relist as they are reopened."""
        self._root_store.remove_all()
        if self.root is None:
            return
        for node in self._list_directory(""):
            self._root_store.append(node)

    def _list_directory(self, rel: str) -> list[TreeNode]:
        directory = self.root / rel if rel else self.root
        directories: list[TreeNode] = []
        files: list[TreeNode] = []
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name.casefold())
        except OSError:
            return []
        for entry in entries:
            if not self.show_hidden and entry.name.startswith("."):
                continue
            child_rel = f"{rel}/{entry.name}" if rel else entry.name
            if entry.is_dir(follow_symlinks=False):
                directories.append(TreeNode(self.root, child_rel, True))
            elif entry.is_file(follow_symlinks=False):
                name = entry.name.casefold()
                readable = name.endswith(NOTE_EXTENSIONS) or name.endswith((".canvas", ".base"))
                if self.markdown_only and not readable:
                    continue
                files.append(TreeNode(self.root, child_rel, False))
        return directories + files

    def _children(self, node: TreeNode):
        if not node.is_dir:
            return None
        store = Gio.ListStore(item_type=TreeNode)
        for child in self._list_directory(node.rel):
            store.append(child)
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
