"""Renders a note's structure — headings and nested bullets — as a mind-map SVG.

The layout is a right-growing tidy tree: leaves claim rows, parents center on
their children, and each depth gets a column sized to its longest label. All
text is escaped; heading nodes link to their anchors in the rendered note.
"""

import html
import os
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from .links import slugify

MAX_NODES = int(os.environ.get("READER_MAX_MINDMAP_NODES", "500"))
MAX_LABEL_CHARS = 60

ROW_HEIGHT = 34.0
COLUMN_GAP = 46.0
CHAR_WIDTH = 7.3
PADDING = 14.0
MARGIN = 30.0

# One hue per depth, readable on light and dark backgrounds alike.
_PALETTE = ["#e05561", "#d18f52", "#4aa96c", "#0f9bd7", "#8a7bdc", "#c678dd"]

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(?:\[.\]\s+)?(.+?)\s*$")
_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_CLEAN = re.compile(r"\[\[([^\]|]*\|)?([^\]]+)\]\]|[*_`]|\[(.+?)\]\([^)]*\)")


@dataclass
class MindNode:
    """One node: its label, link anchor, depth, and children in note order."""

    label: str
    anchor: str = ""
    children: list["MindNode"] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0


def build_tree(title: str, body: str) -> MindNode:
    """Builds the tree: headings by level, then bullets nested by indentation."""
    root = MindNode(label=_clean(title))
    heading_stack: list[tuple[int, MindNode]] = [(0, root)]
    bullet_stack: list[tuple[int, MindNode]] = []
    count = 0
    fence = ""
    anchor_counts: dict[str, int] = {}
    for line in body.split("\n"):
        match = _FENCE.match(line)
        if match:
            marker = match.group(1)
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
            continue
        if fence or count >= MAX_NODES:
            continue
        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            base = slugify(heading.group(2))
            anchor_counts[base] = anchor_counts.get(base, 0) + 1
            anchor = base if anchor_counts[base] == 1 else f"{base}-{anchor_counts[base]}"
            node = MindNode(label=_clean(heading.group(2)), anchor=anchor)
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            parent = heading_stack[-1][1] if heading_stack else root
            parent.children.append(node)
            heading_stack.append((level, node))
            bullet_stack = []
            count += 1
            continue
        bullet = _BULLET.match(line)
        if bullet:
            indent = len(bullet.group(1).expandtabs(4))
            node = MindNode(label=_clean(bullet.group(2)))
            while bullet_stack and bullet_stack[-1][0] >= indent:
                bullet_stack.pop()
            parent = bullet_stack[-1][1] if bullet_stack else heading_stack[-1][1]
            parent.children.append(node)
            bullet_stack.append((indent, node))
            count += 1
    return root


def mindmap_body(title: str, body: str, rel: str) -> str:
    """Lays the tree out and renders the SVG page body."""
    root = build_tree(title, body)
    if not root.children:
        return (
            '<div class="message-state"><h1>Nothing to map</h1>'
            "<p>This note has no headings or list items.</p></div>"
        )
    _measure(root)
    columns = _column_widths(root)
    next_row = [0.0]
    _layout(root, 0, columns, next_row)
    height = next_row[0] * ROW_HEIGHT + 2 * MARGIN
    width = sum(columns) + COLUMN_GAP * len(columns) + 2 * MARGIN
    shapes: list[str] = []
    _draw(root, 0, rel, shapes)
    return (
        f'<div class="mindmap"><svg width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="{-MARGIN:.0f} {-MARGIN:.0f} {width:.0f} {height:.0f}">'
        f"{''.join(shapes)}</svg></div>"
    )


def _clean(text: str) -> str:
    def replace(match: re.Match) -> str:
        return match.group(2) or match.group(3) or ""

    cleaned = _CLEAN.sub(replace, text).strip()
    if len(cleaned) > MAX_LABEL_CHARS:
        cleaned = cleaned[: MAX_LABEL_CHARS - 1] + "…"
    return cleaned or "…"


def _measure(node: MindNode) -> None:
    node.width = len(node.label) * CHAR_WIDTH + 2 * PADDING
    for child in node.children:
        _measure(child)


def _column_widths(root: MindNode) -> list[float]:
    widths: list[float] = []

    def visit(node: MindNode, depth: int) -> None:
        while len(widths) <= depth:
            widths.append(0.0)
        widths[depth] = max(widths[depth], node.width)
        for child in node.children:
            visit(child, depth + 1)

    visit(root, 0)
    return widths


def _layout(node: MindNode, depth: int, columns: list[float], next_row: list[float]) -> None:
    node.x = sum(columns[:depth]) + COLUMN_GAP * depth
    if not node.children:
        node.y = next_row[0] * ROW_HEIGHT
        next_row[0] += 1.0
        return
    for child in node.children:
        _layout(child, depth + 1, columns, next_row)
    node.y = (node.children[0].y + node.children[-1].y) / 2


def _draw(node: MindNode, depth: int, rel: str, shapes: list[str]) -> None:
    color = _PALETTE[depth % len(_PALETTE)]
    right = node.x + node.width
    for child in node.children:
        mid = (right + child.x) / 2
        child_color = _PALETTE[(depth + 1) % len(_PALETTE)]
        shapes.append(
            f'<path d="M {right:.1f} {node.y + ROW_HEIGHT / 2:.1f} '
            f"C {mid:.1f} {node.y + ROW_HEIGHT / 2:.1f} {mid:.1f} "
            f'{child.y + ROW_HEIGHT / 2:.1f} {child.x:.1f} {child.y + ROW_HEIGHT / 2:.1f}" '
            f'fill="none" stroke="{child_color}" stroke-width="1.6" opacity="0.7" />'
        )
        _draw(child, depth + 1, rel, shapes)
    label = html.escape(node.label)
    box = (
        f'<rect x="{node.x:.1f}" y="{node.y + 3:.1f}" width="{node.width:.1f}" '
        f'height="{ROW_HEIGHT - 6:.1f}" rx="9" fill="none" stroke="{color}" '
        'stroke-width="1.6" />'
        f'<text x="{node.x + PADDING:.1f}" y="{node.y + ROW_HEIGHT / 2 + 4.5:.1f}" '
        f'font-size="13">{label}</text>'
    )
    if node.anchor:
        href = html.escape(f"reader:///note/{quote(rel)}#{quote(node.anchor)}", quote=True)
        shapes.append(f'<a href="{href}">{box}</a>')
    else:
        shapes.append(box)
