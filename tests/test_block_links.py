"""Block ids: the block carries its anchor, and a link to it lands there."""

from solander.core.render import NoteRenderer


def render(vault, vault_dir, rel, text):
    (vault_dir / rel).write_text(text)
    vault.reindex()
    return NoteRenderer(vault).render(rel).body


def test_a_paragraph_carries_its_block_id_and_hides_the_marker(vault):
    body = NoteRenderer(vault).render("Projects/Alpha.md").body
    assert '<p id="block-intro">Intro paragraph.</p>' in body
    assert "^intro" not in body


def test_a_link_to_a_block_in_another_note_keeps_the_block(vault, vault_dir):
    body = render(vault, vault_dir, "Linker.md", "See [[Alpha#^intro]].\n")
    assert 'href="reader:///note/Projects/Alpha.md#block-intro"' in body


def test_a_link_to_a_block_in_the_same_note_has_a_target(vault, vault_dir):
    body = render(vault, vault_dir, "Same.md", "Target text. ^here\n\nBack to [[#^here]].\n")
    assert 'href="#block-here"' in body
    assert '<p id="block-here">Target text.</p>' in body


def test_a_marker_on_the_paragraphs_last_line_names_the_paragraph(vault, vault_dir):
    body = render(vault, vault_dir, "Lines.md", "First line\nsecond line\n^both\n")
    assert '<p id="block-both">First line' in body
    assert "^both" not in body


def test_a_list_item_carries_its_block_id(vault, vault_dir):
    body = render(vault, vault_dir, "List.md", "- one\n- two ^second\n- three\n")
    assert '<li id="block-second">two</li>' in body


def test_a_marker_on_its_own_line_names_the_block_before_it(vault, vault_dir):
    text = "| a | b |\n|---|---|\n| 1 | 2 |\n\n^grid\n\n- x\n- y\n\n^items\n"
    body = render(vault, vault_dir, "Blocks.md", text)
    assert '<table id="block-grid"' in body
    assert '<ul id="block-items">' in body
    assert "^grid" not in body
    assert "^items" not in body


def test_a_quote_and_a_callout_carry_their_block_ids(vault, vault_dir):
    text = "> Quoted.\n\n^quote\n\n> [!note] Heads up\n> Body.\n\n^call\n"
    body = render(vault, vault_dir, "Quotes.md", text)
    assert '<blockquote id="block-quote">' in body
    assert 'id="block-call"' in body
    assert 'class="callout callout-note"' in body


def test_a_marker_that_follows_nothing_is_hidden(vault, vault_dir):
    body = render(vault, vault_dir, "Lone.md", "^orphan\n\nText.\n")
    assert "^orphan" not in body
    assert "Text." in body


def test_a_marker_in_code_is_code(vault, vault_dir):
    body = render(vault, vault_dir, "Code.md", "```\nx ^kept\n```\n")
    assert "x ^kept" in body
    assert "block-kept" not in body


def test_a_caret_inside_a_sentence_is_text(vault, vault_dir):
    body = render(vault, vault_dir, "Caret.md", "Two ^squared is four.\n")
    assert "Two ^squared is four." in body


def test_a_heading_loses_the_marker_and_keeps_its_own_anchor(vault, vault_dir):
    body = render(vault, vault_dir, "Head.md", "## Plans ^plan\n")
    assert '<h2 id="plans">Plans</h2>' in body


def test_an_embedded_note_does_not_repeat_its_block_ids(vault, vault_dir):
    body = render(vault, vault_dir, "Embeds.md", "Mine. ^intro\n\n![[Alpha]]\n")
    assert body.count('id="block-intro"') == 1
    assert "^intro" not in body
