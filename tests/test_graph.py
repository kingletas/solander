"""The link graph: backlinks with context, outgoing links, and the tag map."""

from obsidian_reader.core.graph import VaultGraph, local_neighbors, scan_note


def test_backlinks_point_at_the_linking_note(vault):
    graph = VaultGraph.build(vault)
    mentions = graph.backlinks["Projects/Alpha.md"]
    assert all(m.source == "Index.md" for m in mentions)
    assert len(mentions) == 4


def test_backlink_context_carries_the_line(vault):
    graph = VaultGraph.build(vault)
    contexts = [m.context for m in graph.backlinks["Projects/Alpha.md"]]
    assert any("the alias" in context for context in contexts)


def test_embeds_count_as_backlinks(vault):
    graph = VaultGraph.build(vault)
    assert any(
        m.source == "Personal/Cycle A.md" for m in graph.backlinks["Personal/Cycle B.md"]
    )


def test_links_inside_fenced_code_are_ignored(vault, vault_dir):
    (vault_dir / "Fenced.md").write_text("```\n[[Projects/Alpha]]\n```\n`[[Projects/Alpha]]`\n")
    vault.reindex()
    graph = VaultGraph.build(vault)
    assert all(m.source != "Fenced.md" for m in graph.backlinks.get("Projects/Alpha.md", []))


def test_links_inside_comments_are_ignored(vault, vault_dir):
    (vault_dir / "Commented.md").write_text("%%[[Projects/Alpha]]%%\n<!-- [[Projects/Alpha]] -->\n")
    vault.reindex()
    graph = VaultGraph.build(vault)
    assert all(m.source != "Commented.md" for m in graph.backlinks.get("Projects/Alpha.md", []))


def test_outgoing_records_resolution_kinds(vault):
    graph = VaultGraph.build(vault)
    kinds = {link.target: link.kind for link in graph.outgoing["Index.md"]}
    assert kinds["Projects/Alpha"] == "note"
    assert kinds["Nowhere To Be Found"] == "missing"
    assert kinds["Meeting Notes"] == "ambiguous"


def test_tags_come_from_body_and_frontmatter(vault):
    graph = VaultGraph.build(vault)
    assert "Index.md" in graph.tags["home"]
    assert "Index.md" in graph.tags["project/tag"]


def test_nested_tags_match_their_parent(vault):
    graph = VaultGraph.build(vault)
    assert "Index.md" in graph.notes_tagged("project")


def test_heading_hashes_are_not_tags(vault, vault_dir):
    (vault_dir / "Headed.md").write_text("# Heading\n\nSee [[Alpha#Timeline]].\n")
    vault.reindex()
    graph = VaultGraph.build(vault)
    assert "heading" not in graph.tags
    assert "timeline" not in graph.tags


def test_media_embeds_stay_out_of_the_graph(vault):
    graph = VaultGraph.build(vault)
    targets = [link.target for link in graph.outgoing["Index.md"]]
    assert "diagram.png" not in targets


def test_mentions_per_target_are_capped(vault, vault_dir, monkeypatch):
    import obsidian_reader.core.graph as graph_module

    monkeypatch.setattr(graph_module, "MAX_MENTIONS_PER_TARGET", 5)
    (vault_dir / "Spam.md").write_text("[[Projects/Alpha]] " * 50)
    vault.reindex()
    graph = VaultGraph.build(vault)
    assert len(graph.backlinks["Projects/Alpha.md"]) == 5


def test_scan_and_assemble_match_the_direct_build(vault):
    scans = {}
    for rel in vault.notes:
        scans[rel] = scan_note(vault.read_note(rel).text)
    assembled = VaultGraph.assemble(vault, scans)
    direct = VaultGraph.build(vault)
    assert assembled.backlinks == direct.backlinks
    assert assembled.outgoing == direct.outgoing
    assert assembled.tags == direct.tags


def test_frontmatter_tags_read_inline_and_flow_forms(vault, vault_dir):
    (vault_dir / "Inline.md").write_text("---\ntags: [alpha, beta-two]\n---\nBody.\n")
    (vault_dir / "Single.md").write_text("---\ntag: gamma\n---\nBody.\n")
    vault.reindex()
    graph = VaultGraph.build(vault)
    assert "Inline.md" in graph.tags["alpha"]
    assert "Inline.md" in graph.tags["beta-two"]
    assert "Single.md" in graph.tags["gamma"]


def test_frontmatter_tags_read_unindented_lists_with_blank_lines(vault, vault_dir):
    (vault_dir / "Loose.md").write_text("---\ntags:\n\n- delta\n- epsilon\nother: x\n---\nBody.\n")
    vault.reindex()
    graph = VaultGraph.build(vault)
    assert "Loose.md" in graph.tags["delta"]
    assert "Loose.md" in graph.tags["epsilon"]


def test_local_neighbors_orders_both_in_out(vault):
    graph = VaultGraph.build(vault)
    neighbors = dict(local_neighbors(graph, "Personal/Cycle A.md"))
    assert neighbors["Personal/Cycle B.md"] == "both"
    index_neighbors = dict(local_neighbors(graph, "Projects/Alpha.md"))
    assert index_neighbors["Index.md"] == "in"
