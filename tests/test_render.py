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


def test_inert_fences_do_not_execute(vault):
    body = rendered(vault).body
    assert "dataview — not executed in read-only mode" in body
    assert "TABLE file.mtime" in body


def test_code_fence_is_highlighted(vault):
    body = rendered(vault).body
    assert 'class="language-python"' in body


def test_properties_panel_renders_frontmatter(vault):
    page = rendered(vault)
    assert page.properties["title"] == "Index"
    assert 'class="properties"' in page.body


def test_outline_lists_headings_with_anchors(vault):
    outline = rendered(vault, "Projects/Alpha.md").outline
    assert [h.text for h in outline] == ["Alpha", "Timeline", "Notes"]
    assert outline[1].anchor == "timeline"


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
