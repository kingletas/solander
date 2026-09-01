"""Frontmatter splitting under well-formed, malformed, and absent YAML."""

from obsidian_reader.core.frontmatter import split_frontmatter


def test_splits_properties_from_body():
    note = split_frontmatter("---\ntitle: Hello\ntags:\n  - a\n---\nBody text.\n")
    assert note.properties == {"title": "Hello", "tags": ["a"]}
    assert note.body == "Body text.\n"


def test_no_frontmatter_returns_whole_body():
    note = split_frontmatter("Just text.\n---\nnot frontmatter\n")
    assert note.properties == {}
    assert note.body.startswith("Just text.")


def test_malformed_yaml_degrades_to_empty_properties():
    note = split_frontmatter("---\n{unclosed: [\n---\nBody.\n")
    assert note.properties == {}
    assert note.body == "Body.\n"


def test_non_mapping_yaml_degrades_to_empty_properties():
    note = split_frontmatter("---\n- just\n- a list\n---\nBody.\n")
    assert note.properties == {}


def test_unterminated_frontmatter_is_body():
    note = split_frontmatter("---\ntitle: dangling\nno close\n")
    assert note.properties == {}
    assert "dangling" in note.body
