"""The full rendering pipeline against the fixture vault."""

from obsidian_reader.core.render import NoteRenderer, build_message_page, build_source_page


def rendered(vault, rel="Index.md"):
    return NoteRenderer(vault).render(rel)


def test_wikilinks_resolve_to_reader_uris(vault):
    body = rendered(vault).body
    assert 'href="reader:///note/Projects/Alpha.md"' in body
    assert ">the alias</a>" in body
    assert "#timeline" in body


def test_missing_link_is_marked_not_navigable(vault):
    body = rendered(vault).body
    assert 'class="wikilink missing"' in body
    assert "Nowhere To Be Found" in body


def test_ambiguous_link_routes_to_the_chooser(vault):
    body = rendered(vault).body
    assert "reader:///ambiguous/Meeting%20Notes" in body


def test_highlight_comment_and_tag_render(vault):
    body = rendered(vault).body
    assert "<mark>highlight</mark>" in body
    assert "hidden inline" not in body
    assert "a hidden block" not in body
    assert '<span class="tag">#project/tag</span>' in body


def test_task_states_render_distinctly(vault):
    body = rendered(vault).body
    assert 'class="task-list-item"' in body or "task-list-item" in body
    assert "task-cancelled" in body
    assert "task-in-progress" in body
    assert "cancelled task" in body


def test_callouts_render_foldable_and_nested(vault):
    body = rendered(vault).body
    assert '<details class="callout callout-warning"' in body
    assert "Folded warning" in body
    assert 'class="callout callout-note"' in body
    assert 'class="callout callout-tip"' in body


def test_callout_head_does_not_leak_into_the_body(vault):
    body = rendered(vault).body
    assert "[!warning]" not in body
    assert "[!note]" not in body
    assert "Careful with" in body
    assert "Nested callout." in body


def test_html_comments_are_hidden(vault):
    (vault.root / "commented.md").write_text(
        "Before <!--n:some/path-->42 after.\n\n<!-- toc:start -->\n- item\n<!-- toc:end -->\n\n"
        "```text\n<!-- kept in code -->\n```\n"
    )
    body = rendered(vault, "commented.md").body
    assert "toc:start" not in body
    assert "n:some/path" not in body
    assert "Before 42 after." in body
    assert "&lt;!-- kept in code --&gt;" in body


def test_image_embed_uses_vault_scheme_and_size(vault):
    body = rendered(vault).body
    assert 'src="vault:///assets/diagram.png"' in body
    assert 'width="300"' in body


def test_section_embed_renders_only_that_section(vault):
    body = rendered(vault).body
    assert "Ships soon." in body
    assert "Intro paragraph" not in body


def test_cyclic_embed_is_stopped(vault):
    body = rendered(vault, "Personal/Cycle A.md").body
    assert "Cyclic embed" in body


def test_embed_amplification_is_capped(vault, monkeypatch):
    monkeypatch.setattr("obsidian_reader.core.render.MAX_EMBEDS_PER_PAGE", 10)
    (vault.root / "Leaf.md").write_text("leaf text\n")
    (vault.root / "Mid.md").write_text("![[Leaf]]\n\n" * 8)
    (vault.root / "Top.md").write_text("![[Mid]]\n\n" * 8)
    vault.reindex()
    body = rendered(vault, "Top.md").body
    assert "Embed limit for this page reached" in body
    assert body.count("leaf text") <= 10


def test_a_normal_page_never_sees_the_embed_limit(vault):
    body = rendered(vault).body
    assert "Embed limit" not in body


def test_dataview_without_a_graph_degrades_to_inert_source(vault):
    body = rendered(vault).body
    assert "dataview — the index is still building" in body
    assert "TABLE file.mtime" in body


def test_dataview_with_a_graph_renders_a_table(vault):
    from obsidian_reader.core.graph import VaultGraph

    graph = VaultGraph.build(vault)
    renderer = NoteRenderer(vault, graph_provider=lambda: graph)
    body = renderer.render("Index.md").body
    assert "dataview — the index is still building" not in body
    assert '<div class="dataview"><table>' in body


def test_code_fence_is_highlighted(vault):
    body = rendered(vault).body
    assert 'class="language-python"' in body


def test_properties_panel_renders_frontmatter(vault):
    page = rendered(vault)
    assert page.properties["title"] == "Index"
    assert 'class="properties"' in page.body


def test_outline_lists_headings_with_anchors(vault):
    # The leading "# Alpha" repeats the filename, so the header carries it
    # and the outline starts at the sections.
    outline = rendered(vault, "Projects/Alpha.md").outline
    assert [h.text for h in outline] == ["Timeline", "Notes"]
    assert outline[0].anchor == "timeline"


def test_remote_image_is_blocked(vault):
    (vault.root / "remote.md").write_text("![x](https://evil.example/x.png)\n")
    body = rendered(vault, "remote.md").body
    assert "Remote image blocked" in body
    assert "evil.example" in body
    assert "<img" not in body


def test_raw_html_in_notes_is_escaped_to_inert_text(vault):
    (vault.root / "hostile.md").write_text('<script>alert(1)</script>\n<b onclick="x">hi</b>\n')
    body = rendered(vault, "hostile.md").body
    assert "<script" not in body
    assert "<b" not in body
    assert 'onclick="' not in body
    assert "&lt;script&gt;" in body


def test_javascript_href_cannot_become_a_live_link(vault):
    (vault.root / "hostile2.md").write_text("[click](javascript:alert(1))\n")
    body = rendered(vault, "hostile2.md").body
    assert "href=\"javascript" not in body
    assert "<a" not in body


def test_file_scheme_links_are_disarmed(vault):
    (vault.root / "hostile3.md").write_text("[leak](file:///etc/passwd)\n")
    body = rendered(vault, "hostile3.md").body
    assert 'href="file' not in body
    assert "<a" not in body


def test_html_in_a_filename_cannot_break_out(vault):
    hostile = "<img src=x onerror=alert(1)>"
    (vault.root / f"{hostile}.md").write_text("# safe body\n")
    (vault.root / "linker.md").write_text(f"[[{hostile}]]\n")
    vault.reindex()
    page = rendered(vault, f"{hostile}.md")
    assert "<img" not in page.page
    assert 'onerror="' not in page.page
    body = rendered(vault, "linker.md").body
    assert "<img" not in body
    assert 'onerror="' not in body
    assert "&lt;img" in body


def test_unreadable_note_returns_an_error_page(vault):
    page = NoteRenderer(vault).render("ghost.md")
    assert page.error
    assert "Cannot open note" in page.page


def test_helper_pages_build(vault):
    assert "raw-source" in build_source_page("# src", "T")
    assert "message-state" in build_message_page("Empty", "Nothing here")


def test_preview_renders_the_opening_of_a_note(vault):
    page = NoteRenderer(vault).render_preview("Projects/Alpha.md")
    assert "<h1>Alpha</h1>" in page
    assert "Intro paragraph" in page


def test_preview_truncates_a_long_note(vault, vault_dir):
    (vault_dir / "Long.md").write_text("word\n" * 5000)
    vault.reindex()
    page = NoteRenderer(vault).render_preview("Long.md")
    assert "preview-more" in page
    assert page.count("word") < 1000


def test_preview_of_an_unreadable_note_names_the_failure(vault):
    page = NoteRenderer(vault).render_preview("Missing.md")
    assert "Cannot preview" in page


def test_inline_math_renders_mathml(vault, vault_dir):
    (vault_dir / "Math.md").write_text("Euler: $e^{i\\pi} + 1 = 0$ inline.\n")
    vault.reindex()
    body = NoteRenderer(vault).render("Math.md").body
    assert "<math" in body
    assert 'display="inline"' in body


def test_block_math_renders_display_mathml(vault, vault_dir):
    (vault_dir / "Math.md").write_text("$$\n\\frac{a}{b}\n$$\n")
    vault.reindex()
    body = NoteRenderer(vault).render("Math.md").body
    assert 'class="math-block"' in body
    assert "<mfrac>" in body


def test_currency_is_not_math(vault, vault_dir):
    (vault_dir / "Money.md").write_text("It costs $5 and $10 at most. Escaped \\$x\\$ too.\n")
    vault.reindex()
    body = NoteRenderer(vault).render("Money.md").body
    assert "<math" not in body
    assert "$5 and $10" in body


def test_bad_tex_falls_back_to_source(vault, vault_dir):
    (vault_dir / "Math.md").write_text("$\\begin{oops$ and $" + "x" * 6000 + "$\n")
    vault.reindex()
    body = NoteRenderer(vault).render("Math.md").body
    assert "<math" not in body


# -- the note header, "On this page" rail, and linked-mentions footer -------


def test_nested_note_gets_breadcrumb_and_one_title(vault):
    page = NoteRenderer(vault).render("Projects/Alpha.md").page
    assert 'class="crumbs"' in page
    assert "reader:///action/reveal-folder?arg=Projects" in page
    # The body opens with "# Alpha"; the header carries the title and the
    # body's duplicate is stripped, so it appears exactly once.
    assert '<h1 class="inline-title">Alpha</h1>' in page
    assert page.count(">Alpha</h1>") == 1


def test_root_note_gets_inline_title_and_no_breadcrumb(vault):
    page = NoteRenderer(vault).render("Index.md").page
    assert 'class="crumbs"' not in page
    assert '<h1 class="inline-title">Index</h1>' in page


def test_meta_line_counts_words_and_links_tags(vault):
    page = NoteRenderer(vault).render("Index.md").page
    assert "words</span>" in page
    assert "reader:///action/tag?arg=home" in page
    assert "Updated " in page


def test_backlinks_footer_lists_linked_mentions(vault):
    from obsidian_reader.core.graph import VaultGraph

    graph = VaultGraph.build(vault)
    renderer = NoteRenderer(vault, graph_provider=lambda: graph)
    page = renderer.render("Projects/Alpha.md").page
    assert 'class="backlinks"' in page
    assert "reader:///note/Index.md" in page
    without_mentions = renderer.render("Index.md").page
    assert 'class="backlinks"' not in without_mentions


def test_note_context_elements_honor_their_toggles(vault):
    from obsidian_reader.core.graph import VaultGraph

    graph = VaultGraph.build(vault)
    options = {"breadcrumb": False, "meta": False, "backlinks": False}
    renderer = NoteRenderer(vault, graph_provider=lambda: graph, options=lambda: options)
    page = renderer.render("Projects/Alpha.md").page
    assert 'class="crumbs"' not in page
    assert '<h1 class="inline-title">' not in page
    assert 'class="note-meta"' not in page
    assert 'class="backlinks"' not in page
    options.update({"breadcrumb": True, "meta": True, "backlinks": True})
    page = renderer.render("Projects/Alpha.md").page
    assert 'class="crumbs"' in page
    assert 'class="note-meta"' in page
    assert 'class="backlinks"' in page
