"""Wikilink parsing, slugs, and name normalization."""

from obsidian_reader.core.links import normalize_name, parse_embed, parse_wikilink, slugify


def test_parses_a_plain_target():
    link = parse_wikilink("Project Plan")
    assert link.target == "Project Plan"
    assert link.label == "Project Plan"


def test_parses_alias_anchor_and_block():
    link = parse_wikilink("Projects/Alpha#Implementation Plan|Read the plan")
    assert link.target == "Projects/Alpha"
    assert link.anchor == "Implementation Plan"
    assert link.alias == "Read the plan"
    assert link.label == "Read the plan"

    block = parse_wikilink("Alpha#^intro")
    assert block.block_id == "intro"
    assert block.anchor == ""


def test_escaped_pipe_separates_the_alias():
    link = parse_wikilink("Note\\|Shown")
    assert link.target == "Note"
    assert link.alias == "Shown"


def test_local_anchor_only_link():
    link = parse_wikilink("#Current Heading")
    assert link.target == ""
    assert link.anchor == "Current Heading"
    assert link.label == "Current Heading"


def test_embed_numeric_alias_is_a_size():
    embed = parse_embed("diagram.png|300")
    assert embed.size == "300"
    assert embed.alias == ""
    assert parse_embed("diagram.png|640x480").size == "640x480"
    assert parse_embed("Note|A real alias").alias == "A real alias"


def test_slugify_matches_case_and_punctuation_loosely():
    assert slugify("Implementation Plan") == "implementation-plan"
    assert slugify("What's next?") == "whats-next"
    assert slugify("Ünïcode Héading") == slugify("ünïcode héading")
    assert slugify("!!!") == "section"


def test_normalize_name_strips_extension_and_case():
    assert normalize_name("Alpha.md") == normalize_name("alpha")
    assert normalize_name("Café.md") == normalize_name("Café")
