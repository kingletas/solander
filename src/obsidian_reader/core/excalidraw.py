"""Renders Excalidraw notes as static SVG: shapes, arrows, strokes, and text.

The drawing JSON (LZ-String compressed or plain) is untrusted vault content:
coordinates go through float(), colors through a hex check, text through
escaping — app-authored markup, like canvas and message pages.
"""

import html
import json
import os
import re

from .lzstring import decompress_base64

MAX_DRAWING_BYTES = int(os.environ.get("READER_MAX_DRAWING_BYTES", str(10 * 1024 * 1024)))
MAX_ELEMENTS = int(os.environ.get("READER_MAX_DRAWING_ELEMENTS", "3000"))

MARGIN = 40.0

_COMPRESSED = re.compile(r"```compressed-json\n(.*?)```", re.DOTALL)
_PLAIN = re.compile(r"```json\n(.*?)```", re.DOTALL)
_HEX = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def excalidraw_body(text: str) -> str:
    """Renders the drawing embedded in an Excalidraw note, or names why it cannot."""
    payload = None
    match = _COMPRESSED.search(text)
    if match:
        payload = decompress_base64(match.group(1))
        if payload is None:
            return _message("The compressed drawing data could not be decoded")
    else:
        match = _PLAIN.search(text)
        if match:
            payload = match.group(1)
    if payload is None:
        return _message("This note has no drawing data")
    if len(payload) > MAX_DRAWING_BYTES:
        return _message("This drawing is too large to render")
    try:
        data = json.loads(payload)
    except ValueError:
        return _message("The drawing data is not valid JSON")
    elements = data.get("elements") if isinstance(data, dict) else None
    if not isinstance(elements, list):
        return _message("The drawing has no elements")
    return _svg(elements[:MAX_ELEMENTS])


def _svg(elements: list) -> str:
    shapes = []
    bounds: list[float] = []
    for element in elements:
        if not isinstance(element, dict) or element.get("isDeleted"):
            continue
        try:
            shape, box = _element(element)
        except (KeyError, TypeError, ValueError):
            continue
        if shape:
            shapes.append(shape)
            bounds.extend(box)
    if not shapes:
        return _message("The drawing has no renderable elements")
    xs = bounds[0::2]
    ys = bounds[1::2]
    min_x, max_x = min(xs) - MARGIN, max(xs) + MARGIN
    min_y, max_y = min(ys) - MARGIN, max(ys) + MARGIN
    width = max_x - min_x
    height = max_y - min_y
    return (
        f'<div class="excalidraw"><svg width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="{min_x:.0f} {min_y:.0f} {width:.0f} {height:.0f}">'
        '<defs><marker id="xarrow" markerWidth="10" markerHeight="8" refX="8" refY="4" '
        'orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="currentColor" /></marker></defs>'
        f"{''.join(shapes)}</svg></div>"
    )


def _element(element: dict) -> tuple[str, list[float]]:
    kind = element.get("type")
    x = float(element["x"])
    y = float(element["y"])
    width = float(element.get("width", 0))
    height = float(element.get("height", 0))
    stroke = _color(element.get("strokeColor"), "currentColor")
    fill = _color(element.get("backgroundColor"), "none")
    stroke_width = min(max(float(element.get("strokeWidth", 1)), 0.5), 8.0)
    opacity = min(max(float(element.get("opacity", 100)) / 100.0, 0.0), 1.0)
    common = (
        f'stroke="{stroke}" fill="{fill}" stroke-width="{stroke_width}" opacity="{opacity}"'
    )
    transform = _rotation(element, x, y, width, height)
    box = [x, y, x + width, y + height]
    if kind == "rectangle":
        return (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
            f'rx="6" {common}{transform} />',
            box,
        )
    if kind == "ellipse":
        return (
            f'<ellipse cx="{x + width / 2:.1f}" cy="{y + height / 2:.1f}" '
            f'rx="{width / 2:.1f}" ry="{height / 2:.1f}" {common}{transform} />',
            box,
        )
    if kind == "diamond":
        points = (
            f"{x + width / 2:.1f},{y:.1f} {x + width:.1f},{y + height / 2:.1f} "
            f"{x + width / 2:.1f},{y + height:.1f} {x:.1f},{y + height / 2:.1f}"
        )
        return f'<polygon points="{points}" {common}{transform} />', box
    if kind == "text":
        size = float(element.get("fontSize", 16))
        lines = str(element.get("text", "")).split("\n")
        spans = "".join(
            f'<tspan x="{x:.1f}" dy="{size * 1.25 if index else size:.1f}">'
            f"{html.escape(line) or ' '}</tspan>"
            for index, line in enumerate(lines)
        )
        return (
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.0f}" '
            f'fill="{stroke}" opacity="{opacity}"{transform}>{spans}</text>',
            box,
        )
    if kind in ("arrow", "line", "freedraw", "draw"):
        raw_points = element.get("points") or []
        points = []
        for pair in raw_points:
            points.append(f"{x + float(pair[0]):.1f},{y + float(pair[1]):.1f}")
            box = box + [x + float(pair[0]), y + float(pair[1])]
        if len(points) < 2:
            return "", box
        marker = ' marker-end="url(#xarrow)"' if kind == "arrow" else ""
        return (
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{stroke}" '
            f'stroke-width="{stroke_width}" opacity="{opacity}" '
            f'stroke-linejoin="round" stroke-linecap="round"{marker}{transform} />',
            box,
        )
    return "", box


def _rotation(element: dict, x: float, y: float, width: float, height: float) -> str:
    angle = float(element.get("angle", 0))
    if not angle:
        return ""
    degrees = angle * 180.0 / 3.141592653589793
    return f' transform="rotate({degrees:.1f} {x + width / 2:.1f} {y + height / 2:.1f})"'


def _color(value, fallback: str) -> str:
    if isinstance(value, str):
        if _HEX.match(value):
            return value
        if value == "transparent":
            return "none"
    return fallback


def _message(text: str) -> str:
    return (
        '<div class="message-state"><h1>Cannot render drawing</h1>'
        f"<p>{html.escape(text)}</p></div>"
    )
