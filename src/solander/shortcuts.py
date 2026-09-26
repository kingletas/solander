"""The keys the window binds, and the list the shortcuts window shows for them.

Both are plain data, kept apart from GTK so the test suite can check that every
bound key is listed and every listed key is bound.
"""

ACCELERATORS: dict[str, tuple[str, ...]] = {
    "open-file": ("<Control>o",),
    "open-vault": ("<Control><Shift>o",),
    "find": ("<Control>f",),
    "quick-open": ("<Control>p",),
    "search-vault": ("<Control><Shift>f",),
    "reload": ("<Control>r", "F5"),
    "back": ("<Alt>Left",),
    "forward": ("<Alt>Right",),
    "toggle-sidebar": ("F9",),
    "toggle-outline": ("F8",),
    "new-tab": ("<Control>t",),
    "close-tab": ("<Control>w",),
    "zen": ("F11",),
    "leave-zen": ("Escape",),
    "export-pdf": ("<Control><Shift>e",),
    "mindmap": ("<Control>m",),
    "zoom-in": ("<Control>plus", "<Control>equal"),
    "zoom-out": ("<Control>minus",),
    "zoom-reset": ("<Control>0",),
    "user-guide": ("F1",),
    "shortcuts": ("<Control>question",),
    "toggle-source": ("<Control>u",),
}
"""GTK accelerator strings for each window action, bound as `win.<action>`."""

SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("Ctrl+O", "Open file"),
    ("Ctrl+Shift+O", "Open vault folder"),
    ("Ctrl+P or Ctrl+Shift+F", "Search: names as you type, full text on Enter"),
    ("Ctrl+F", "Find within note"),
    ("Ctrl+R or F5", "Reload current note"),
    ("Ctrl+U", "Toggle raw source view"),
    ("Alt+Left / Alt+Right", "Back / Forward"),
    ("Ctrl+T / Ctrl+W", "New tab / Close tab"),
    ("Middle-click or Ctrl+click", "Open a note, link or search result in a new tab"),
    ("Right-click a search result", "Open it in a new tab"),
    ("Right-click a folder", "Read it as a book, or hide it (Preferences unhides)"),
    ("F8", "Toggle the outline panel"),
    ("F9", "Toggle sidebar"),
    ("F11 / Esc", "Reading mode in / out"),
    ("Ctrl+M", "View the note as a mind map"),
    ("N, Space, Right, Down, Page Down", "Book: turn forward"),
    ("P, Left, Up, Page Up", "Book: turn back"),
    ("Esc", "Book: close it"),
    ("Ctrl+Shift+E", "Export as PDF"),
    ("Ctrl++ or Ctrl+=", "Zoom in"),
    ("Ctrl+- / Ctrl+0", "Zoom out / reset"),
    ("F1", "User guide"),
    ("Ctrl+?", "This window"),
)
"""What the shortcuts window lists, in order: keys on the left, what they do on the right.

The book keys and the mouse gestures are handled by event controllers rather than
accelerators, so the test cannot check those rows and they are kept by hand.
"""
