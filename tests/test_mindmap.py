"""The mind-map builder: tree shape, labels, anchors, and the SVG output."""

from solander.core.mindmap import build_tree, mindmap_body

BODY = (
    "# Top\n\n"
    "## First\n\n- alpha\n- beta\n    - beta child\n\n"
    "## Second\n\ntext\n\n- [ ] task item\n\n"
    "```\n# not a heading\n- not a bullet\n```\n\n"
    "### Deep [[Some Note|linked]] *emphasis*\n"
)


def test_tree_nests_headings_and_bullets():
    root = build_tree("Note", BODY)
    top = root.children[0]
    assert top.label == "Top"
    first = top.children[0]
    assert [child.label for child in first.children] == ["alpha", "beta"]
    assert first.children[1].children[0].label == "beta child"
    second = top.children[1]
    assert second.children[0].label == "task item"
    assert second.children[1].label == "Deep linked emphasis"


def test_fenced_content_is_ignored():
    root = build_tree("Note", BODY)
    labels = []

    def collect(node):
        labels.append(node.label)
        for child in node.children:
            collect(child)

    collect(root)
    assert "not a heading" not in labels


def test_svg_output_links_headings_and_escapes():
    body = mindmap_body("My Note", "# A & B\n\n- <script>\n", "Dir/My Note.md")
    assert "<svg" in body
    assert "A &amp; B" in body
    assert "&lt;script&gt;" in body
    assert 'href="reader:///note/Dir/My%20Note.md#a-b"' in body


def test_empty_note_gets_a_message():
    assert "Nothing to map" in mindmap_body("X", "just prose\n", "X.md")


def test_mindmap_page_carries_a_back_link(vault):
    from solander.core.render import NoteRenderer

    page = NoteRenderer(vault).render_mindmap("Index.md")
    assert 'href="reader:///note/Index.md">\u25c0 Back to Index</a>' in page
