"""The fewest edits that turn one ordered list into another.

A list view keeps what it knows about a row, such as whether a folder is expanded,
only while that row survives. Replacing every row to show one new file throws that
away, so a refresh applies these edits instead and leaves unchanged rows alone.
"""

from collections.abc import Hashable, Sequence
from difflib import SequenceMatcher


def splices(
    old: Sequence[Hashable], new: Sequence[Hashable]
) -> list[tuple[int, int, int, int]]:
    """Edits as (position, removed, new_start, new_end), last first, so positions stay valid.

    Applying one means removing `removed` items at `position` and inserting
    `new[new_start:new_end]` there. Items the two lists share in order are never touched.
    """
    edits = [
        (i1, i2 - i1, j1, j2)
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
        if tag != "equal"
    ]
    return edits[::-1]
