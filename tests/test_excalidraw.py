"""LZ-String decoding and the Excalidraw SVG renderer."""

import json

from obsidian_reader.core.excalidraw import excalidraw_body
from obsidian_reader.core.lzstring import decompress_base64


def wrap(elements) -> str:
    payload = json.dumps({"elements": elements})
    return f"---\nexcalidraw-plugin: parsed\n---\n\n```json\n{payload}\n```\n"


def test_malformed_compressed_payload_degrades():
    text = "---\nexcalidraw-plugin: parsed\n---\n```compressed-json\n!!notbase64!!\n```\n"
    assert "could not be decoded" in excalidraw_body(text)


def test_decompress_rejects_garbage_and_accepts_empty():
    assert decompress_base64("") == ""
    assert decompress_base64("!!!") is None


def test_shapes_text_and_arrows_render():
    body = excalidraw_body(wrap([
        {"type": "rectangle", "x": 0, "y": 0, "width": 100, "height": 50,
         "strokeColor": "#1e1e1e", "backgroundColor": "transparent"},
        {"type": "text", "x": 10, "y": 10, "width": 80, "height": 20,
         "text": "Hello <b>", "fontSize": 16},
        {"type": "arrow", "x": 100, "y": 25, "width": 50, "height": 0,
         "points": [[0, 0], [50, 0]]},
        {"type": "diamond", "x": 0, "y": 100, "width": 40, "height": 40},
    ]))
    assert "<rect" in body and "<polygon" in body
    assert "Hello &lt;b&gt;" in body
    assert 'marker-end="url(#xarrow)"' in body


def test_hostile_values_are_neutralized():
    body = excalidraw_body(wrap([
        {"type": "rectangle", "x": 0, "y": 0, "width": 10, "height": 10,
         "strokeColor": 'red" onload="alert(1)'},
        {"type": "rectangle", "x": "NaN-ish", "y": 0, "width": 10, "height": 10},
        {"type": "text", "x": 0, "y": 30, "width": 10, "height": 10,
         "text": "</svg><script>x</script>"},
    ]))
    assert "onload" not in body
    assert "<script>" not in body
    assert 'stroke="currentColor"' in body


def test_deleted_elements_are_skipped():
    body = excalidraw_body(wrap([
        {"type": "rectangle", "x": 0, "y": 0, "width": 10, "height": 10, "isDeleted": True},
    ]))
    assert "no renderable elements" in body
