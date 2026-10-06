"""The only scripts the window runs in a note's page, and how they are built.

Page JavaScript is off: nothing a note contains can run. The window runs these
three in a script world of its own, which sees the same document without giving
the note a way in. Nothing from a note or from saved state reaches them as text:
one is a constant, the others format a number, and a test fails if the window
ever passes anything else.
"""

SCRIPT_WORLD = "solander"

READ_SCROLL = (
    "(() => { const room = document.documentElement.scrollHeight - window.innerHeight;"
    " return String(room > 0 ? window.scrollY / room : 0); })()"
)
"""How far down the page is, from 0 at the top to 1 at the end, as text."""


def restore_scroll(fraction: float) -> str:
    """The script that scrolls a page to `fraction` of the way down.

    The value is formatted as a number, so anything that is not one raises here
    rather than becoming script.
    """
    return (
        "window.scrollTo(0, "
        f"{float(fraction):.5f} * (document.documentElement.scrollHeight - window.innerHeight))"
    )


def block_text(index: int) -> str:
    """The script that reads the text of the page's fenced block number `index`.

    The number is formatted as a whole number, so anything that is not one raises
    here rather than becoming script. A page with no such block answers nothing.
    """
    return (
        "(() => { const link = document.querySelectorAll('a.copy-block')"
        f"[{int(index):d}];"
        " const block = link && link.parentElement.querySelector('pre');"
        " return block ? block.textContent : ''; })()"
    )
