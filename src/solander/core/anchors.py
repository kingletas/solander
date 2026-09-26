"""The element ids a page gives its headings and blocks, kept from colliding."""

from .hits import FIRST_HIT_ID
from .links import slugify

BLOCK_PREFIX = "block-"


def heading_anchor(heading: str) -> str:
    """The id a heading renders with, and a link to it points at.

    Blocks own the `block-` prefix and search owns its first-hit id, so a heading
    that slugs into either is moved aside rather than taking a landing spot a note
    could otherwise choose for itself.
    """
    base = slugify(heading)
    if base == FIRST_HIT_ID or base.startswith(BLOCK_PREFIX):
        return f"h-{base}"
    return base


def block_anchor(block_id: str) -> str:
    """The id a `^block-id` renders as, and a link to it points at."""
    return f"{BLOCK_PREFIX}{block_id}"
