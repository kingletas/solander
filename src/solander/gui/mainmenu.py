"""The main menu as a Gio.Menu, built from the table glossa shares with the other reading app.

The table says which groups and rows there are, in which order and in which words. This
builds the toolkit menu from it, for the capabilities the window holds.
"""

from collections.abc import Collection, Mapping

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib
from glossa.menu import Group, Item, main_menu


def build_main_menu(
    capabilities: Collection[str],
    app_name: str,
    leaves: Mapping[str, str | Gio.Menu],
) -> Gio.Menu:
    """The menu this window offers. A leaf is a row only this app can fill: an action name
    to run, or a page to drill into."""
    return _fill(main_menu(capabilities, app_name), leaves, top=True)


def _fill(groups: tuple[Group, ...], leaves: Mapping[str, str | Gio.Menu], top: bool) -> Gio.Menu:
    menu = Gio.Menu()
    # A page made of one group with no heading is just its rows; the first level and any page
    # with headings keep their groups as sections.
    flat = not top and len(groups) == 1 and not groups[0].heading
    for group in groups:
        section = menu if flat else Gio.Menu()
        for item in group.items:
            _append(section, item, leaves)
        if not flat:
            menu.append_section(group.heading or None, section)
    return menu


def _append(menu: Gio.Menu, item: Item, leaves: Mapping[str, str | Gio.Menu]) -> None:
    if item.custom:
        row = Gio.MenuItem.new(None, None)
        row.set_attribute_value("custom", GLib.Variant.new_string(item.custom))
        menu.append_item(row)
    elif item.submenu:
        menu.append_submenu(item.label, _fill(item.submenu, leaves, top=False))
    elif item.leaf:
        destination = leaves[item.leaf]
        if isinstance(destination, Gio.Menu):
            menu.append_submenu(item.label, destination)
        else:
            menu.append(item.label, destination)
    else:
        menu.append(item.label, item.action)
