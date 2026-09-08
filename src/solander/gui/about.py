"""About: what this reader is, and what it will not do to the vault it has open.

The version and the licence are the same in every copy. What is specific to this
one is the vault it is reading and the promise it can make about it, so that is
the body of the dialog rather than a line at the bottom of it.
"""

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from ..core.session import describe_run

HOME = "https://github.com/kingletas/solander"
"""The same address the metainfo gives, so the two cannot say different things."""

TAGLINE = "read-only Obsidian vault reader"

DOES = "Reads your vault in place and keeps its own index."
CANNOT = "Cannot change your notes, reach the network, or run another program."
"""Not generated: this reader has one composition and it is the whole design."""

WHAT_IT_IS = (
    "A solander is the clamshell box an archive keeps its documents in: open it "
    "to look at something, close it, and nothing has changed."
)


class AboutDialog(Adw.Dialog):
    """What this reader is and what it promises, in that order."""

    def __init__(self, window, app_name: str, app_id: str, version: str):
        super().__init__(title=f"About {app_name}", content_width=440)
        self.window = window
        self.details = _system_details(window, version)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for margin in ("top", "bottom", "start", "end"):
            getattr(body, f"set_margin_{margin}")(18)
        body.append(_masthead(app_name, app_id, version))
        body.append(_running())
        explanation = Gtk.Label(label=WHAT_IT_IS, xalign=0.0, wrap=True)
        explanation.add_css_class("dim-label")
        body.append(explanation)
        body.append(_vault_label(window))
        body.append(self._copy_button())
        body.append(Gtk.Separator())
        body.append(self._links())

        scroller = Gtk.ScrolledWindow(child=body, propagate_natural_height=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        view = Adw.ToolbarView(content=scroller)
        view.add_top_bar(Adw.HeaderBar())
        self.set_child(view)

    def _copy_button(self) -> Gtk.Widget:
        content = Adw.ButtonContent(icon_name="edit-copy-symbolic", label="Copy system details")
        button = Gtk.Button(child=content, halign=Gtk.Align.START)
        button.add_css_class("suggested-action")
        button.connect("clicked", lambda *_: self._copy())
        return button

    def _copy(self) -> None:
        display = Gdk.Display.get_default()
        if display is not None:
            display.get_clipboard().set(self.details)
        self.window.add_toast(Adw.Toast(title="System details copied"))

    def _links(self) -> Gtk.Widget:
        """The two guides live inside the app, so they are buttons rather than links."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class("about-links")
        for said, action in (("Getting started", "getting-started"), ("Guide", "user-guide")):
            button = Gtk.Button(label=said)
            button.add_css_class("flat")
            button.connect("clicked", self._open_page, action)
            row.append(button)
        for said, where in (("Source", HOME), ("Report a problem", f"{HOME}/issues")):
            link = Gtk.LinkButton(uri=where, label=said)
            link.add_css_class("flat")
            row.append(link)
        return row

    def _open_page(self, _button, action: str) -> None:
        self.close()
        self.window.activate_action(f"win.{action}", None)


def _masthead(app_name: str, app_id: str, version: str) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.append(Gtk.Image(icon_name=app_id, pixel_size=72))
    name = Gtk.Label(label=app_name)
    name.add_css_class("about-name")
    box.append(name)
    line = Gtk.Label(label=f"Version {version} · {TAGLINE}")
    line.add_css_class("dim-label")
    box.append(line)
    return box


def _running() -> Gtk.Widget:
    """The card: what this reader does, then in bold what it will not do."""
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    card.add_css_class("card")
    card.add_css_class("running-card")
    heading = Gtk.Label(label="Running right now", xalign=0.0)
    heading.add_css_class("panel-heading")
    card.append(heading)
    card.append(Gtk.Label(label=DOES, xalign=0.0, wrap=True))
    promise = Gtk.Label(label=CANNOT, xalign=0.0, wrap=True)
    promise.add_css_class("promise")
    card.append(promise)
    return card


def _vault_label(window) -> Gtk.Widget:
    """Which vault is open, by its name rather than by where it is kept.

    The name answers the question; the path answers it and also says how somebody
    files their own notes, which is theirs and not this dialog's to publish. The
    recent-vaults menu has always named them this way.
    """
    vault = getattr(window, "vault", None)
    said = Path(vault.root).name if vault is not None else "No vault open"
    label = Gtk.Label(label=said, xalign=0.0, wrap=True, selectable=True)
    label.add_css_class("dim-label")
    label.add_css_class("composition-path")
    return label


def _system_details(window, version: str) -> str:
    """What this run is, taken from the window and worded by the core."""
    vault = getattr(window, "vault", None)
    notes = len(vault.notes) if vault is not None else None
    return describe_run(version, notes, window.store.state.theme)
