"""The canvas renderer: parsing, escaping, and hostile geometry."""

import json

from obsidian_reader.core.canvas import canvas_body, parse_canvas

SIMPLE = {
    "nodes": [
        {"id": "a", "type": "text", "x": 0, "y": 0, "width": 200, "height": 60,
         "text": "Hello <script>alert(1)</script>"},
        {"id": "b", "type": "file", "x": 300, "y": 0, "width": 200, "height": 60,
         "file": "Projects/Alpha.md"},
        {"id": "g", "type": "group", "x": -20, "y": -20, "width": 560, "height": 120,
         "label": "Group & label"},
    ],
    "edges": [{"id": "e", "fromNode": "a", "toNode": "b", "fromSide": "right", "toSide": "left"}],
}


def render(payload):
    return canvas_body(parse_canvas(json.dumps(payload)), lambda rel: f"reader:///note/{rel}")


def test_nodes_edges_and_groups_render():
    body = render(SIMPLE)
    assert body.count("canvas-card") == 2
    assert "canvas-group" in body
    assert "<line" in body
    assert 'href="reader:///note/Projects/Alpha.md"' in body


def test_text_is_escaped():
    body = render(SIMPLE)
    assert "<script>" not in body
    assert "&lt;script&gt;" in body
    assert "Group &amp; label" in body


def test_malformed_json_degrades():
    assert parse_canvas("{not json").error
    assert parse_canvas(json.dumps({"nodes": "nope"})).error
    assert parse_canvas(json.dumps({"nodes": []})).error


def test_hostile_geometry_is_refused_per_node():
    payload = {"nodes": [
        {"id": "a", "type": "text", "x": "NaN-ish", "y": 0, "width": 1, "height": 1},
        {"id": "b", "type": "text", "x": 0, "y": 0, "width": 100, "height": 50, "text": "ok"},
    ]}
    canvas = parse_canvas(json.dumps(payload))
    assert [node.id for node in canvas.nodes] == ["b"]


def test_edges_to_unknown_nodes_are_dropped():
    payload = dict(SIMPLE)
    payload["edges"] = [{"fromNode": "a", "toNode": "ghost"}]
    canvas = parse_canvas(json.dumps(payload))
    assert canvas.edges == []


def test_color_is_palette_or_hex_only():
    payload = {"nodes": [
        {"id": "a", "type": "text", "x": 0, "y": 0, "width": 1, "height": 1, "color": "1"},
        {"id": "b", "type": "text", "x": 0, "y": 0, "width": 1, "height": 1,
         "color": "red;} body{display:none"},
    ]}
    canvas = parse_canvas(json.dumps(payload))
    colors = {node.id: node.color for node in canvas.nodes}
    assert colors["a"].startswith("#")
    assert colors["b"] == ""
