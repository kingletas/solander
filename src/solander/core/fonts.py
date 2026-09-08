"""The two faces the design is set in, and the two ways they have to be reached.

They are bundled because neither ships with a Linux desktop, and a page that falls
back to whatever is installed is a different design. The page loads them through
`@font-face` over the client's own scheme; the window chrome cannot, because GTK
resolves a family name through fontconfig and cannot see package data — so the
same files are also pointed at by a fontconfig fragment.
"""

import os
from importlib import resources
from pathlib import Path

PACKAGE = "solander.assets"
"""Where the files sit; the same package the stylesheets are read from."""

FACES = (
    ("Manrope", "Manrope-Variable.ttf", "normal", "200 800"),
    ("Literata", "Literata-Variable.ttf", "normal", "200 900"),
    ("Literata", "Literata-Italic-Variable.ttf", "italic", "200 900"),
)
"""Family, file, style and the weight range each variable face actually covers."""

MIME = "font/ttf"
"""One format rather than two: fontconfig cannot read WOFF2, and these are local."""


def font_css(prefix: str) -> str:
    """The `@font-face` rules, with each file addressed the way this client serves it."""
    rules = []
    for family, filename, style, weights in FACES:
        rules.append(
            f"@font-face {{\n"
            f"  font-family: '{family}';\n"
            f"  src: url('{prefix}{filename}') format('truetype');\n"
            f"  font-style: {style};\n"
            f"  font-weight: {weights};\n"
            f"  font-display: swap;\n"
            f"}}"
        )
    return "\n".join(rules)


def font_bytes(filename: str) -> bytes | None:
    """One bundled font file, or nothing at all for a name that is not one of ours.

    The name is matched against the list rather than joined onto a path, so a
    request cannot walk out of the package however it is spelled.
    """
    if filename not in {name for _, name, _, _ in FACES}:
        return None
    return resources.files(PACKAGE).joinpath("fonts", filename).read_bytes()


def fontconfig_fragment(directory: str) -> str:
    """A fontconfig file naming the bundled directory, for a run from a checkout.

    An installed copy puts the files on a real font path instead; this is what
    lets the chrome wear the same faces as the page without installing anything.
    """
    return (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
        "<fontconfig>\n"
        "  <include ignore_missing=\"yes\">/etc/fonts/fonts.conf</include>\n"
        f"  <dir>{directory}</dir>\n"
        "</fontconfig>\n"
    )


def teach_fontconfig() -> None:
    """Points fontconfig at the bundled directory, for a run from a checkout.

    GTK resolves a family name through fontconfig, which cannot see package data,
    so a chrome asking for Manrope gets Cantarell unless the files are on a font
    path. An installation puts them on one; this covers the run that has not
    been installed. It must happen before the first GTK import, and it stands
    aside for a FONTCONFIG_FILE somebody set on purpose.
    """
    if os.environ.get("FONTCONFIG_FILE"):
        return
    directory = resources.files(PACKAGE).joinpath("fonts")
    if not directory.is_dir():
        return
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "solander"
    fragment = cache / "fonts.conf"
    try:
        cache.mkdir(parents=True, exist_ok=True)
        fragment.write_text(fontconfig_fragment(str(directory)), "utf-8")
    except OSError:
        # A read-only cache is not a reason to refuse to start: the chrome falls
        # back to Cantarell and the page still loads the faces over its scheme.
        return
    os.environ["FONTCONFIG_FILE"] = str(fragment)
