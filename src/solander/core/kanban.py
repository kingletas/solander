"""Renders obsidian-kanban board notes as read-only column layouts.

A board is plain markdown — `## Column` headings with task-list cards — plus
`kanban-plugin` frontmatter. The card text is rendered inline by the caller's
parser, so wikilinks inside cards resolve like anywhere else.
"""

import html
import re
from dataclasses import dataclass, field

_HEADING = re.compile(r"^##\s+(.+?)\s*$")
_CARD = re.compile(r"^- \[(.)\] (.+)$")
_ARCHIVE_RULE = re.compile(r"^\*\*\*+\s*$")


@dataclass
class KanbanColumn:
    """One lane: its title and card texts in board order."""

    title: str
    cards: list[tuple[str, str]] = field(default_factory=list)


def parse_kanban(body: str) -> list[KanbanColumn]:
    """Splits a board body into columns; everything after `***` is the archive."""
    columns: list[KanbanColumn] = []
    current: KanbanColumn | None = None
    archived = False
    for line in body.split("\n"):
        if _ARCHIVE_RULE.match(line):
            archived = True
            current = KanbanColumn(title="Archive")
            columns.append(current)
            continue
        heading = _HEADING.match(line)
        if heading and not archived:
            current = KanbanColumn(title=heading.group(1))
            columns.append(current)
            continue
        card = _CARD.match(line.strip())
        if card and current is not None:
            current.cards.append((card.group(1), card.group(2).strip()))
    return columns


def kanban_body(columns: list[KanbanColumn], render_inline) -> str:
    """Builds the board markup; `render_inline` turns card markdown into safe HTML."""
    if not columns:
        return '<div class="message-state"><h1>Empty board</h1></div>'
    lanes = []
    for column in columns:
        cards = []
        for status, text in column.cards:
            done = " kanban-done" if status.casefold() == "x" else ""
            cards.append(f'<div class="kanban-card{done}">{render_inline(text)}</div>')
        count = f'<span class="kanban-count">{len(column.cards)}</span>'
        lanes.append(
            f'<div class="kanban-column"><div class="kanban-column-title">'
            f"{html.escape(column.title)} {count}</div>{''.join(cards)}</div>"
        )
    return f'<div class="kanban">{"".join(lanes)}</div>'
