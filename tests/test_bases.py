"""The Bases renderer: table views, filters, formulas, groups, limits, and plugin-view refusals."""

import re
import time

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
    assert "tasknotesKanban plugin view, which is not rendered" in markup


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


# A subject page in the shape of a real one: every note in a project's folder, or
# naming it, or linking into it, sorted into kinds by a formula.
SUBJECT = """
filters:
  and:
    - or:
        - file.inFolder("Projects")
        - project == "Alpha"
        - formula.links_in
    - not:
        - file.inFolder("Personal")
        - file.basename == "Skip"
formulas:
  links_in: file.links.filter(value.asFile() && value.asFile().inFolder("Projects")).length > 0
  kind: if(file.inFolder("Projects"), "Project", if(file.inFolder("Record"), "Record", "Other"))
  shouted: upper(formula.kind)
properties:
  formula.kind:
    displayName: Kind
views:
  - type: table
    name: Recent
    filters:
      and:
        - file.mtime > now() - "1d"
    order:
      - file.name
      - formula.kind
    sort:
      - property: file.name
        direction: ASC
    limit: 2
  - type: table
    name: By kind
    groupBy:
      property: formula.kind
      direction: ASC
    order:
      - file.name
      - formula.shouted
"""


def subject_graph(vault, vault_dir):
    (vault_dir / "Record").mkdir()
    (vault_dir / "Projects" / "Beta.md").write_text("# B\n")
    (vault_dir / "Record" / "Links In.md").write_text("Points at [[Projects/Beta]].\n")
    (vault_dir / "Record" / "Names It.md").write_text("---\nproject: Alpha\n---\n# N\n")
    (vault_dir / "Record" / "Unrelated.md").write_text("Points at [[Index]].\n")
    (vault_dir / "Record" / "Skip.md").write_text("Points at [[Projects/Beta]].\n")
    (vault_dir / "Loose.md").write_text("Points at [[Projects/Alpha]].\n")
    vault.reindex()
    graph = VaultGraph.build(vault)
    now = time.time()
    old = now - 3 * 86400
    graph.meta = {rel: (old, 1) for rel in graph.props}
    for rel in ("Projects/Beta.md", "Record/Links In.md", "Loose.md"):
        graph.meta[rel] = (now - 3600, 1)
    return graph


def names(section: str) -> list[str]:
    return re.findall(r'href="reader:///note/([^"]+)"', section)


def views(markup: str) -> dict[str, str]:
    parts = re.split(r"<h2>(.*?)</h2>", markup)
    return dict(zip(parts[1::2], parts[2::2], strict=True))


def test_formulas_select_rows_by_what_a_note_links_to(vault, vault_dir):
    markup = render_base(subject_graph(vault, vault_dir), SUBJECT)
    rows = names(views(markup)["By kind"])
    assert sorted(rows) == sorted([
        "Projects/Alpha.md", "Projects/Beta.md", "Projects/Meeting%20Notes.md",
        "Record/Links%20In.md", "Record/Names%20It.md", "Loose.md", "Index.md",
    ])
    assert "Unrelated" not in markup
    assert "Skip" not in markup


def test_group_by_a_formula_with_counts_in_order(vault, vault_dir):
    section = views(render_base(subject_graph(vault, vault_dir), SUBJECT))["By kind"]
    groups = re.findall(r'<tr class="base-group"><th colspan="2">(.*?)</th>', section)
    assert groups == ["Other (2)", "Project (3)", "Record (2)"]
    assert section.index("Loose.md") < section.index("Projects/Beta.md")
    assert "<td>PROJECT</td>" in section


def test_limit_and_a_duration_string_beside_a_date(vault, vault_dir):
    section = views(render_base(subject_graph(vault, vault_dir), SUBJECT))["Recent"]
    assert names(section) == ["Projects/Beta.md", "Record/Links%20In.md"]
    assert "Showing the first 2 rows" in section
    assert "<th>Kind</th>" in section


def test_a_formula_that_reaches_itself_is_named_not_looped(vault, vault_dir):
    base = """
formulas:
  a: formula.b
  b: formula.a
views:
  - type: table
    name: Loop
    order:
      - file.name
      - formula.a
"""
    markup = render_base(make_graph(vault, vault_dir), base)
    assert "not evaluated" in markup
    assert "refers to itself" in markup


def test_an_unreadable_formula_says_which(vault, vault_dir):
    base = """
formulas:
  broken: if(
views:
  - type: table
    name: Any
"""
    markup = render_base(make_graph(vault, vault_dir), base)
    assert "formula that cannot be read" in markup
    assert "broken" in markup
