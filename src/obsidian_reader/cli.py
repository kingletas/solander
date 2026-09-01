"""Command-line entry point: version, path arguments, and a friendly bindings check."""

import sys

from . import __version__

USAGE = """\
obsidian-reader [PATH]

Opens PATH as a vault (directory) or a note (.md file) in a read-only reader.
With no PATH, reopens the last session.

Options:
  --version   print the version and exit
  -h, --help  this text
"""


def main() -> int:
    """Parses the trivial flags, then hands the real arguments to the GTK application."""
    arguments = sys.argv[1:]
    if "--version" in arguments:
        print(f"obsidian-reader {__version__}")
        return 0
    if "-h" in arguments or "--help" in arguments:
        print(USAGE, end="")
        return 0
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        gi.require_version("WebKit", "6.0")
    except (ImportError, ValueError) as error:
        print(
            "obsidian-reader needs the system GTK bindings:\n"
            "  sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0\n"
            f"({error})",
            file=sys.stderr,
        )
        return 1
    from .gui.app import ReaderApplication

    return ReaderApplication().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
