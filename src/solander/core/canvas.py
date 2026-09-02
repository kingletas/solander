"""Renders an Obsidian `.canvas` file as a static page: positioned cards over SVG edges.

The canvas is untrusted vault content, so every coordinate is forced through
`float()`, every color through a fixed palette or hex check, and every string
through `html.escape` — the markup here is the app's own, like a message page.
"""

import html
import json
import os
from dataclasses import dataclass, field

MAX_CANVAS_BYTES = int(os.environ.get("READER_MAX_CANVAS_BYTES", str(5 * 1024 * 1024)))
MAX_CANVAS_NODES = int(os.environ.get("READER_MAX_CANVAS_NODES", "1000"))

MARGIN = 60.0

# Obsidian's six named canvas colors, in its own order.
_PALETTE = {
    "1": "#e93147", "2": "#ec7500", "3": "#e0ac00",
    "4": "#08b94e", "5": "#00bfbc", "6": "#7852ee",
}


@dataclass(frozen=True)
class CanvasNode:
    """One canvas card: geometry, kind, and its escaped display content."""

    id: str
    x: float
    y: float
    width: float
    height: float
    kind: str
    text: str = ""
    file: str = ""
    label: str = ""
    color: str = ""


@dataclass(frozen=True)
class CanvasEdge:
    """One arrow between two nodes, with the side each end attaches to."""

    from_node: str
    to_node: str
    from_side: str = "right"
    to_side: str = "left"
    label: str = ""


@dataclass
class Canvas:
    """A parsed canvas, or the reason it could not be parsed."""

    nodes: list[CanvasNode] = field(default_factory=list)
    edges: list[CanvasEdge] = field(default_factory=list)
    error: str = ""


def parse_canvas(raw: str) -> Canvas:
    """Parses canvas JSON defensively; anything malformed degrades to an error."""
    if len(raw.encode("utf-8", errors="replace")) > MAX_CANVAS_BYTES:
        return Canvas(error="This canvas is too large to render")
    try:
        data = json.loads(raw)
    except ValueError:
        return Canvas(error="This canvas is not valid JSON")
    if not isinstance(data, dict):
        return Canvas(error="This canvas has no nodes")
    canvas = Canvas()
    nodes = data.get("nodes")
    for entry in nodes if isinstance(nodes, list) else []:
        if not isinstance(entry, dict) or len(canvas.nodes) >= MAX_CANVAS_NODES:
            continue
        try:
            node = CanvasNode(
                id=str(entry.get("id", "")),
                x=float(entry["x"]),
                y=float(entry["y"]),
                width=float(entry["width"]),
                height=float(entry["height"]),
                kind=str(entry.get("type", "text")),
                text=str(entry.get("text", "")),
                file=str(entry.get("file", "")),
                label=str(entry.get("label", "")),
                color=_safe_color(entry.get("color")),
            )
        except (KeyError, TypeError, ValueError):
            continue
        canvas.nodes.append(node)
    edges = data.get("edges")
    known = {node.id for node in canvas.nodes}
    for entry in edges if isinstance(edges, list) else []:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("fromNode", ""))
        target = str(entry.get("toNode", ""))
        if source in known and target in known:
            canvas.edges.append(
                CanvasEdge(
                    from_node=source,
                    to_node=target,
                    from_side=str(entry.get("fromSide", "right")),
                    to_side=str(entry.get("toSide", "left")),
                    label=str(entry.get("label", "")),
                )
            )
    if not canvas.nodes:
        return Canvas(error="This canvas has no nodes")
    return canvas


def canvas_body(canvas: Canvas, note_href) -> str:
    """Builds the page body: an SVG edge layer under absolutely positioned cards.

    `note_href` maps a vault-relative file path to an internal link, or "".
    """
    if canvas.error:
        return (
            '<div class="message-state"><h1>Cannot render canvas</h1>'
            f"<p>{html.escape(canvas.error)}</p></div>"
        )
    min_x = min(node.x for node in canvas.nodes) - MARGIN
    min_y = min(node.y for node in canvas.nodes) - MARGIN
    max_x = max(node.x + node.width for node in canvas.nodes) + MARGIN
    max_y = max(node.y + node.height for node in canvas.nodes) + MARGIN
    width = max_x - min_x
    height = max_y - min_y
    by_id = {node.id: node for node in canvas.nodes}

    lines = []
    for edge in canvas.edges:
        x1, y1 = _anchor(by_id[edge.from_node], edge.from_side, min_x, min_y)
        x2, y2 = _anchor(by_id[edge.to_node], edge.to_side, min_x, min_y)
        lines.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            'marker-end="url(#arrow)" />'
        )
        if edge.label:
            lines.append(
                f'<text x="{(x1 + x2) / 2:.1f}" y="{(y1 + y2) / 2 - 6:.1f}">'
                f"{html.escape(edge.label)}</text>"
            )
    svg = (
        f'<svg class="canvas-edges" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}">'
        '<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" '
        'orient="auto"><path d="M0,0 L10,4 L0,8 z" /></marker></defs>'
        f"{''.join(lines)}</svg>"
    )

    cards = []
    ordered = sorted(canvas.nodes, key=lambda node: 0 if node.kind == "group" else 1)
    for node in ordered:
        left = node.x - min_x
        top = node.y - min_y
        style = (
            f"left:{left:.1f}px;top:{top:.1f}px;"
            f"width:{node.width:.1f}px;height:{node.height:.1f}px;"
        )
        if node.color:
            style += f"border-color:{node.color};"
        cards.append(_card(node, style, note_href))

    return (
        f'<div class="canvas" style="width:{width:.0f}px;height:{height:.0f}px">'
        f"{svg}{''.join(cards)}</div>"
    )


def _card(node: CanvasNode, style: str, note_href) -> str:
    if node.kind == "group":
        label = html.escape(node.label)
        return (
            f'<div class="canvas-group" style="{style}">'
            f'<span class="canvas-group-label">{label}</span></div>'
        )
    if node.kind == "file":
        name = html.escape(node.file.rsplit("/", 1)[-1])
        href = note_href(node.file)
        inner = f'<a href="{html.escape(href, quote=True)}">{name}</a>' if href else name
        return f'<div class="canvas-card canvas-file" style="{style}">{inner}</div>'
    if node.kind == "link":
        label = html.escape(node.text or node.label)
        return f'<div class="canvas-card" style="{style}">{label}</div>'
    return f'<div class="canvas-card" style="{style}">{html.escape(node.text)}</div>'


def _anchor(node: CanvasNode, side: str, min_x: float, min_y: float) -> tuple[float, float]:
    left = node.x - min_x
    top = node.y - min_y
    if side == "left":
        return left, top + node.height / 2
    if side == "right":
        return left + node.width, top + node.height / 2
    if side == "top":
        return left + node.width / 2, top
    return left + node.width / 2, top + node.height


def _safe_color(value) -> str:
    if not isinstance(value, str):
        return ""
    if value in _PALETTE:
        return _PALETTE[value]
    if len(value) in (4, 7) and value.startswith("#"):
        if all(c in "0123456789abcdefABCDEF" for c in value[1:]):
            return value
    return ""
