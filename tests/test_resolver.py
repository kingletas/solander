"""Link resolution order, ambiguity refusal, and path-escape handling."""

from obsidian_reader.core.resolver import resolve_attachment, resolve_embed, resolve_note


def test_relative_path_wins_over_name_match(vault):
    resolved = resolve_note(vault, "Projects/Alpha.md", "Meeting Notes")
    assert resolved.kind == "note"
    assert resolved.path == "Projects/Meeting Notes.md"


def test_vault_root_path_resolves(vault):
    resolved = resolve_note(vault, "Index.md", "Projects/Alpha")
    assert resolved.kind == "note"
    assert resolved.path == "Projects/Alpha.md"


def test_filename_match_resolves_from_anywhere(vault):
    resolved = resolve_note(vault, "Index.md", "Alpha")
    assert resolved.kind == "note"
    assert resolved.path == "Projects/Alpha.md"


def test_extension_variants_resolve(vault):
    assert resolve_note(vault, "Index.md", "Alpha.md").path == "Projects/Alpha.md"


def test_ambiguous_name_is_refused_with_candidates(vault):
    resolved = resolve_note(vault, "Index.md", "Meeting Notes")
    assert resolved.kind == "ambiguous"
    assert resolved.candidates == [
        "Personal/Meeting Notes.md",
        "Projects/Meeting Notes.md",
    ]


def test_missing_note_reports_missing(vault):
    assert resolve_note(vault, "Index.md", "No Such Note").kind == "missing"


def test_dotdot_cannot_escape_the_vault(vault):
    assert resolve_note(vault, "Index.md", "../../etc/passwd").kind == "missing"
    assert resolve_attachment(vault, "Index.md", "../../../etc/passwd").kind == "missing"


def test_attachment_folder_is_searched(vault):
    resolved = resolve_attachment(vault, "Projects/Alpha.md", "diagram.png")
    assert resolved.kind == "image"
    assert resolved.path == "assets/diagram.png"


def test_embed_prefers_note_then_falls_back_to_file(vault):
    assert resolve_embed(vault, "Index.md", "Alpha").kind == "note"
    assert resolve_embed(vault, "Index.md", "diagram.png").kind == "image"
    assert resolve_embed(vault, "Index.md", "ghost.png").kind == "missing"
