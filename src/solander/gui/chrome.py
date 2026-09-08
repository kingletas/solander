"""Two strips of the window that report rather than act: the path, and the foot.

The header used to say the note's name and the vault's; Stone says where the note
lives, because that is the question a person opening a vault of nine thousand notes
actually has. The foot says what this composition may do and what is on the page.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

SEPARATOR = "/"
"""What sits between two steps of a path. The vault's own separator, not an arrow."""


class CrumbPath(Gtk.Box):
    """Where the open note lives: its folders quiet, its own name in ink.

    It answers to `set_title` and `set_subtitle` because that is what an
    `Adw.WindowTitle` answers to, and the vault opening reports through those.
    """

    def __init__(self, on_folder=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add_css_class("crumb-path")
        self.set_valign(Gtk.Align.CENTER)
        self._on_folder = on_folder
        self._rel = ""
        self._leaf = ""
        self._status = ""
        self._draw()

    def set_title(self, shown: str) -> None:
        """The note now open, under whatever name the reader shows it by."""
        self._leaf = shown
        self._draw()

    def set_subtitle(self, text: str) -> None:
        """What the header says while no note is open, or while the vault is read."""
        self._status = text
        self._draw()

    def show_note(self, rel: str) -> None:
        """The folders the open note sits in, deepest last."""
        self._rel = rel
        self._draw()

    def steps(self) -> list[str]:
        """The folders above the open note, outermost first."""
        parts = [part for part in self._rel.split("/") if part]
        return parts[:-1] if parts else []

    def _draw(self) -> None:
        child = self.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self.remove(child)
            child = following
        if not self._leaf:
            self.append(self._label(self._status, "crumb-step"))
            return
        walked = ""
        for step in self.steps():
            walked = f"{walked}/{step}" if walked else step
            self.append(self._step(step, walked))
            self.append(self._label(SEPARATOR, "crumb-sep"))
        self.append(self._label(self._leaf, "crumb-leaf"))

    def _label(self, text: str, style: str) -> Gtk.Label:
        # The leaf is the answer to "which note is this"; an ancestor is context,
        # so a header with no room shortens the folders and keeps the name whole.
        label = Gtk.Label(label=text, ellipsize=3 if style == "crumb-step" else 0)
        label.add_css_class(style)
        if style == "crumb-sep":
            label.set_margin_start(5)
            label.set_margin_end(5)
        return label

    def _step(self, step: str, path: str) -> Gtk.Widget:
        """One folder, and a way into it where the window offered one."""
        if self._on_folder is None:
            return self._label(step, "crumb-step")
        button = Gtk.Button(child=self._label(step, "crumb-step"))
        button.add_css_class("flat")
        button.add_css_class("crumb-button")
        button.connect("clicked", lambda _b: self._on_folder(path))
        return button


class ReaderFoot(Gtk.Box):
    """The strip under the page: what this reader may do, and what is on it.

    It reports and never acts. Everything in it is something the window already
    knows, said once, in the place a person looks when they want to check.
    """

    def __init__(self, capability: str):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.add_css_class("reader-foot")
        lock = Gtk.Image(icon_name="changes-prevent-symbolic", pixel_size=12)
        self.capability = Gtk.Label(label=capability, xalign=0)
        self.indexed = Gtk.Label(label="", xalign=0)
        self.measure = Gtk.Label(label="", xalign=1)
        self.theme = Gtk.Label(label="", xalign=1)
        self.dot = Gtk.Box()
        self.dot.add_css_class("theme-dot")
        self.dot.set_valign(Gtk.Align.CENTER)
        self.append(lock)
        self.append(self.capability)
        self.append(self._separator())
        self.append(self.indexed)
        self.append(Gtk.Box(hexpand=True))
        self.append(self.measure)
        self.append(self._separator())
        self.append(self.dot)
        self.append(self.theme)

    def _separator(self) -> Gtk.Label:
        label = Gtk.Label(label="·")
        label.add_css_class("foot-sep")
        return label

    def say_capability(self, sentence: str) -> None:
        self.capability.set_label(sentence)

    def say_indexed(self, notes: int) -> None:
        self.indexed.set_label(f"{notes:,} notes indexed" if notes else "")

    def say_theme(self, label: str) -> None:
        self.theme.set_label(label)

    def say_note(self, words: int) -> None:
        """The size of what is on the page, in the terms a reader thinks in."""
        if not words:
            self.measure.set_label("")
            return
        minutes = max(1, round(words / READING_WORDS_PER_MINUTE))
        self.measure.set_label(f"{words:,} words · {minutes} min read")


READING_WORDS_PER_MINUTE = 220
"""The rate a reading time is worked out at; the same one the page's own line uses."""
