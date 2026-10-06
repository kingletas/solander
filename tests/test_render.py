"""The full rendering pipeline against the fixture vault."""

import re
from importlib import resources

import pytest

from solander.core.render import (
    PROSE_FENCES,
    NoteRenderer,
    build_message_page,
    build_source_page,
    number_copy_links,
)


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
    monkeypatch.setattr("solander.core.render.MAX_EMBEDS_PER_PAGE", 10)
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
    assert "dataview: the index is still building" in body
    assert "TABLE file.mtime" in body


def test_dataview_with_a_graph_renders_a_table(vault):
    from solander.core.graph import VaultGraph

    graph = VaultGraph.build(vault)
    renderer = NoteRenderer(vault, graph_provider=lambda: graph)
    body = renderer.render("Index.md").body
    assert "dataview: the index is still building" not in body
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
    assert 'class="inline-title"' in page


def test_meta_line_counts_words_and_links_tags(vault):
    page = NoteRenderer(vault).render("Index.md").page
    assert "words</span>" in page
    assert "reader:///action/tag?arg=home" in page
    assert "Updated " in page


def test_backlinks_footer_lists_linked_mentions(vault):
    from solander.core.graph import VaultGraph

    graph = VaultGraph.build(vault)
    renderer = NoteRenderer(vault, graph_provider=lambda: graph)
    page = renderer.render("Projects/Alpha.md").page
    assert 'class="backlinks"' in page
    assert "reader:///note/Index.md" in page
    without_mentions = renderer.render("Index.md").page
    assert 'class="backlinks"' not in without_mentions


def test_note_context_elements_honor_their_toggles(vault):
    from solander.core.graph import VaultGraph

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


def test_a_leading_heading_becomes_the_title_and_leaves_the_body(vault):
    """A vault of folder indexes is a vault of notes all called README."""
    page = NoteRenderer(vault).render("Index.md").page
    assert '<h1 class="inline-title">Welcome</h1>' in page
    assert page.count(">Welcome<") == 1


def test_the_metadata_line_reads_the_time_the_walk_recorded(vault):
    """The renderer asks the vault, never the filesystem.

    A storage backend that is not a POSIX filesystem has to answer for the vault
    and nothing else, which only holds while nothing renders around it. The file
    on disk is untouched here, so a renderer that stats it reports this year.
    """
    # Mid-September 2001, so no timezone can move it into another year.
    vault.mtimes["Index.md"] = 1_000_000_000.0
    assert "2001" in rendered(vault, "Index.md").page


def test_a_note_the_walk_never_saw_is_rendered_without_a_time(vault):
    (vault.root / "Unlisted.md").write_text("# Unlisted\n\nSome prose.\n")
    page = rendered(vault, "Unlisted.md")
    assert page.error == ""
    assert "Updated" not in page.page


# -- a client that is not the window ----------------------------------------

BROWSER_BASES = {
    "note": "/note/",
    "asset": "/asset/",
    "action": "",
    "ambiguous": "/ambiguous/",
    "external": "/open/",
    "font": "/font/",
}


def browser_rendered(vault, rel: str):
    """Renders as a client that serves over paths and has no window actions."""
    renderer = NoteRenderer(vault, options=lambda: {"link_bases": BROWSER_BASES})
    return renderer.render(rel)


def test_a_path_client_gets_no_window_schemes_anywhere(vault):
    """An Android or browser WebView cannot register `reader:` or `vault:`.

    A link written in a scheme the client cannot intercept is a dead link, and a
    page that is only mostly free of them is still broken.
    """
    page = browser_rendered(vault, "Index.md").page
    assert "reader:///" not in page
    assert "vault:///" not in page
    assert "/note/" in page


def test_the_bundled_faces_follow_the_client_too(vault):
    """A face is a link like any other: written in a scheme this client cannot
    register, it is a font that never loads and a page set in the fallback."""
    page = browser_rendered(vault, "Index.md").page
    assert "url('/font/Manrope-Variable.ttf')" in page
    assert "font-src 'self';" in page
    window = rendered(vault, "Index.md").page
    assert "url('reader:///font/Manrope-Variable.ttf')" in window
    assert "font-src reader:;" in window


def test_the_window_is_still_served_its_own_schemes(vault):
    page = rendered(vault, "Index.md").page
    assert "reader:///note/" in page


def test_a_client_with_no_actions_writes_them_as_text(vault):
    """A browser cannot reveal a folder in a tree, so it is told, not linked."""
    page = browser_rendered(vault, "Projects/Alpha.md").page
    assert "reveal-folder" not in page
    assert "<span>Projects</span>" in page


def test_dataview_results_follow_the_client_too(vault):
    (vault.root / "Query.md").write_text(
        '```dataview\nLIST FROM "" SORT file.name ASC LIMIT 3\n```\n'
    )
    vault.reindex()
    from solander.core.graph import VaultGraph

    graph = VaultGraph.build(vault)
    renderer = NoteRenderer(
        vault, graph_provider=lambda: graph, options=lambda: {"link_bases": BROWSER_BASES}
    )
    page = renderer.render("Query.md").page
    assert "reader:///" not in page
    assert "/note/" in page


def test_a_mind_map_follows_the_client_too(vault):
    renderer = NoteRenderer(vault, options=lambda: {"link_bases": BROWSER_BASES})
    page = renderer.render_mindmap("Index.md")
    assert "reader:///" not in page
    assert "/note/" in page


def test_a_task_checkbox_is_labelled_by_its_task(vault, vault_dir):
    (vault_dir / "Tasks.md").write_text("- [ ] open one\n- [x] done one\n")
    vault.reindex()
    body = NoteRenderer(vault).render("Tasks.md").body
    box = '<input class="task-list-item-checkbox" disabled type="checkbox" />'
    assert f"<label>{box} open one</label>" in body
    assert "checked disabled" in body and "done one</label>" in body


def test_an_embedded_image_takes_its_caption_as_alt_text(vault, vault_dir):
    (vault_dir / "Pic.md").write_text("![[diagram.png|Sales funnel]]\n\n![[diagram.png]]\n")
    vault.reindex()
    body = NoteRenderer(vault).render("Pic.md").body
    assert 'alt="Sales funnel"' in body
    assert 'alt="diagram.png"' in body


def test_the_page_draws_its_own_keyboard_focus(vault):
    page = NoteRenderer(vault).render("Index.md").page
    assert "a:focus-visible" in page
    assert "outline: 2px solid var(--accent)" in page


def test_a_render_nobody_waits_for_stops_early(vault):
    import pytest

    from solander.core.render import RenderCancelled

    renderer = NoteRenderer(vault)
    with pytest.raises(RenderCancelled):
        renderer.copy(should_stop=lambda: True).render("Index.md")
    assert "Index" in renderer.copy(should_stop=lambda: False).render("Index.md").page


def fenced_page(vault, tag: str, content: str = "one line\n\nand another\n", options=None) -> str:
    renderer = NoteRenderer(vault, options=(lambda: options) if options else None)
    return renderer.render_text(f"```{tag}\n{content}```\n", "Fences")


def test_the_fence_tags_that_count_as_prose_are_these():
    assert PROSE_FENCES == {"", "text", "txt", "plain"}


@pytest.mark.parametrize("tag", ["", "text", "txt", "plain", "TEXT", "Plain"])
def test_a_text_or_untagged_fence_is_marked_as_prose_so_it_wraps(vault, tag):
    page = fenced_page(vault, tag)
    assert '<div class="fenced prose">' in page
    assert "<pre><code>one line\n\nand another\n</code></pre>" in page


@pytest.mark.parametrize("tag", ["python", "bash", "json", "no-such-language"])
def test_a_fence_with_any_other_language_is_not_prose_and_keeps_its_lines(vault, tag):
    page = fenced_page(vault, tag)
    assert '<div class="fenced">' in page
    assert "fenced prose" not in page


def test_a_highlighted_fence_keeps_the_markup_it_had_inside_its_wrapper(vault):
    page = fenced_page(vault, "python", "x = 1\n")
    block = r'<pre class="highlight"><code class="language-python">.*?</code></pre></div>'
    assert re.search(block, page, re.S)


def test_every_fenced_block_carries_a_copy_link_numbered_in_page_order(vault):
    renderer = NoteRenderer(vault)
    text = "```text\na\n```\n\n```python\nb = 1\n```\n\n```\nc\n```\n"
    page = renderer.render_text(text, "Three")
    link = r'<a class="copy-block" href="([^"]*)" title="Copy this block">Copy</a>'
    links = re.findall(link, page)
    assert links == ["reader:///copy/0", "reader:///copy/1", "reader:///copy/2"]


def test_an_embedded_notes_blocks_are_counted_with_the_page_they_land_in(vault_dir):
    from solander.core.vault import Vault

    (vault_dir / "Inner.md").write_text("```text\ninner\n```\n")
    (vault_dir / "Outer.md").write_text("```text\nfirst\n```\n\n![[Inner]]\n\n```text\nlast\n```\n")
    page = NoteRenderer(Vault.open(vault_dir)).render("Outer.md").page
    assert re.findall(r'href="reader:///copy/(\d+)"', page) == ["0", "1", "2"]
    assert page.index("first") < page.index("inner") < page.index("last")


def test_a_note_cannot_write_a_copy_link_of_its_own_into_the_count():
    body = '<p>reader:///copy/</p><a class="copy-block" href="reader:///copy/" title="t">Copy</a>'
    assert number_copy_links(body).count("reader:///copy/0") == 1
    assert "<p>reader:///copy/</p>" in number_copy_links(body)


def test_a_client_that_writes_its_own_links_gets_a_copy_link_only_by_naming_one(vault):
    without = fenced_page(vault, "text", options={"link_bases": BROWSER_BASES})
    assert "copy-block" not in without.split("</style>")[-1]
    assert '<div class="fenced prose"><pre>' in without

    named = fenced_page(vault, "text", options={"link_bases": BROWSER_BASES | {"copy": "/copy/"}})
    assert '<a class="copy-block" href="/copy/0" title="Copy this block">Copy</a>' in named


def test_a_blocks_text_reaches_the_page_escaped_and_whole(vault):
    page = fenced_page(vault, "text", "<b>not bold</b> & kept\n\n  indented\n")
    assert "&lt;b&gt;not bold&lt;/b&gt; &amp; kept\n\n  indented\n</code>" in page


def test_the_stylesheet_wraps_prose_blocks_on_screen_and_every_block_in_print():
    css = resources.files("solander.assets").joinpath("reader.css").read_text(encoding="utf-8")
    assert ".fenced.prose > pre { white-space: pre-wrap;" in css
    assert "  pre { overflow-x: visible; white-space: pre-wrap; word-break: break-word; }" in css
    assert "  a.copy-block { display: none; }" in css


@pytest.mark.parametrize(
    "address",
    [
        "reader:///copy/0",
        "reader:/copy/0",
        "reader:copy/0",
        "READER:///copy/0",
        "reader://anywhere/copy/0",
        "reader:///%63opy/0",
    ],
)
def test_a_link_written_in_a_note_cannot_set_off_a_copy(vault, address):
    text = f"[Open the report]({address})\n\n```text\nthe block\n```\n"
    page = NoteRenderer(vault).render_text(text, "Planted")
    body = page.split("</style>")[-1]
    assert re.findall(r'href="([^"]*)"', body) == ["reader:///copy/0"], "only the block's own link"
    assert "Open the report" in body and "unsupported-link" in body


def test_a_client_with_its_own_copy_base_is_protected_the_same_way(vault):
    options = {"link_bases": BROWSER_BASES | {"copy": "/copy/"}}
    page = fenced_page(vault, "text", "x\n", options=options)
    planted = NoteRenderer(vault, options=lambda: options).render_text("[x](/copy/0)\n", "P")
    assert 'href="/copy/0"' in page
    assert 'href="/copy/0"' not in planted
