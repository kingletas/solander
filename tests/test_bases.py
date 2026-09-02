"""The Bases renderer: table views, filters, sorts, and plugin-view refusals."""

from solander.core.bases import render_base
from solander.core.graph import VaultGraph

BASE = """
properties:
  note.priority:
    displayName: Weight
views:
  - type: table
    name: Open things
    filters:
      and:
        - file.inFolder("Projects")
        - status != "done"
    order:
      - file.name
      - priority
    sort:
      - property: priority
        direction: DESC
  - type: tasknotesKanban
    name: Board
"""


def make_graph(vault, vault_dir):
    (vault_dir / "Projects" / "Beta.md").write_text("---\nstatus: open\npriority: 2\n---\n# B\n")
    (vault_dir / "Projects" / "Gamma.md").write_text("---\nstatus: done\npriority: 5\n---\n# G\n")
    (vault_dir / "Projects" / "Delta.md").write_text("---\nstatus: open\npriority: 9\n---\n# D\n")
    vault.reindex()
    return VaultGraph.build(vault)


def test_table_view_filters_sorts_and_links(vault, vault_dir):
    markup = render_base(make_graph(vault, vault_dir), BASE)
    assert "Gamma" not in markup
    assert markup.index("Delta") < markup.index("Beta")
    assert 'href="reader:///note/Projects/Beta.md"' in markup
    assert "<th>Weight</th>" in markup


def test_plugin_views_are_named_not_faked(vault, vault_dir):
    markup = render_base(make_graph(vault, vault_dir), BASE)
    assert "tasknotesKanban plugin view — not rendered" in markup


def test_malformed_base_degrades(vault, vault_dir):
    graph = make_graph(vault, vault_dir)
    assert "not valid YAML" in render_base(graph, "views: [::")
    assert "no views" in render_base(graph, "properties: {}")


def test_has_tag_and_spaced_columns(vault, vault_dir):
    graph = make_graph(vault, vault_dir)
    base = """
views:
  - type: table
    name: Tagged
    filters:
      and:
        - file.hasTag("home")
    order:
      - file.name
      - Release Name
"""
    markup = render_base(graph, base)
    assert "Index" in markup
    assert "Beta" not in markup
    assert "<th>Release Name</th>" in markup
