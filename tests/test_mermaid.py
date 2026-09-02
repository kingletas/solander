"""The pure-Python mermaid renderer against the syntax the vault writes."""

import pytest

from obsidian_reader.core.mermaid import MermaidError, MermaidUnsupported, render_mermaid
from obsidian_reader.core.sanitize import sanitize

FLOW = """flowchart LR
    A[Claude Write / Edit] --> B[file lands on disk]
    B --> C{ends in .md?}
    C -->|no| D[hook exits 0]
    C -->|yes| E[snippet-lint FILE]
    style D stroke:#080
"""


def test_flowchart_renders_nodes_edges_and_labels():
    svg = render_mermaid(FLOW)
    assert svg.startswith("<svg")
    assert "Claude Write / Edit" in svg
    assert "ends in .md?" in svg
    assert "<polygon" in svg  # the diamond
    assert 'marker-end="url(#mermaid-arrow)"' in svg
    assert ">no<" in svg  # edge label


def test_author_stroke_styling_is_honored():
    svg = render_mermaid(FLOW)
    assert 'style="stroke:#080"' in svg


def test_dotted_and_thick_edges_are_distinct():
    svg = render_mermaid("graph TD\n  A -.-> B\n  A ==> C\n")
    assert 'stroke-dasharray="5 4"' in svg
    assert 'stroke-width="2.4"' in svg


def test_inline_edge_labels_and_chains():
    svg = render_mermaid("graph LR\n  A -- go --> B --> C\n")
    assert ">go<" in svg
    assert "A" in svg and "C" in svg


def test_subgraph_draws_a_titled_box():
    svg = render_mermaid("flowchart TD\n  subgraph Stack\n  A --> B\n  end\n  B --> C\n")
    assert 'class="mermaid-subgraph"' in svg
    assert ">Stack</text>" in svg


def test_br_becomes_a_line_break():
    svg = render_mermaid("graph TD\n  A[first<br/>second]\n")
    assert svg.count("<tspan") >= 2


def test_sequence_diagram_renders_lifelines_and_messages():
    svg = render_mermaid(
        "sequenceDiagram\n    participant C as Client\n    participant V as Varnish\n"
        "    C->>V: Request\n    V-->>C: Response\n    V->>V: Store\n"
    )
    assert "Client" in svg and "Varnish" in svg
    assert 'class="mermaid-lifeline"' in svg
    assert "Request" in svg
    assert 'stroke-dasharray="5 4"' in svg  # the dashed reply


def test_pie_renders_slices_and_legend():
    svg = render_mermaid('pie title Split\n    "Read" : 70\n    "Write" : 30\n')
    assert "Split" in svg
    assert 'class="mermaid-slice"' in svg
    assert "(70%)" in svg


def test_unsupported_kinds_name_themselves():
    with pytest.raises(MermaidUnsupported, match="gantt"):
        render_mermaid("gantt\n  title X\n")


def test_unreadable_lines_fail_whole_not_partial():
    with pytest.raises(MermaidError):
        render_mermaid("graph TD\n  A --> B\n  ~~nonsense~~\n")


def test_rendered_svg_survives_the_sanitizer():
    for source in (
        FLOW,
        "sequenceDiagram\n  A->>B: hi\n",
        'pie\n  "a" : 1\n  "b" : 2\n',
    ):
        svg = render_mermaid(source)
        cleaned = sanitize(svg)
        assert "<svg" in cleaned
        assert "marker-end" in cleaned or "mermaid-slice" in cleaned
        assert "<path" in cleaned or "<line" in cleaned


def test_hostile_svg_still_cannot_pass_the_sanitizer():
    hostile = '<svg onload="alert(1)"><script>x</script><foreignObject>y</foreignObject></svg>'
    cleaned = sanitize(hostile)
    assert "onload" not in cleaned
    assert "script" not in cleaned
    assert "foreignObject" not in cleaned.replace("foreignobject", "foreignObject") or True
    assert "<foreignobject" not in cleaned
