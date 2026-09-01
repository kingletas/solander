"""The vault model: indexing, containment, encoding fallback, config reading."""

from obsidian_reader.core.vault import Vault, file_kind


def test_indexes_notes_and_skips_dot_directories(vault):
    assert "Index.md" in vault.notes
    assert "Projects/Alpha.md" in vault.notes
    assert not any(rel.startswith(".obsidian") for rel in vault.files)


def test_name_lookup_is_case_insensitive(vault):
    assert vault.notes_named("alpha") == ["Projects/Alpha.md"]
    assert vault.notes_named("ALPHA.md") == ["Projects/Alpha.md"]
    assert sorted(vault.notes_named("Meeting Notes")) == [
        "Personal/Meeting Notes.md",
        "Projects/Meeting Notes.md",
    ]


def test_reads_the_configured_attachment_folder(vault):
    assert vault.attachment_folder == "assets"


def test_missing_app_json_falls_back_without_error(tmp_path):
    (tmp_path / "note.md").write_text("hi")
    vault = Vault.open(tmp_path)
    assert vault.attachment_folder == ""


def test_containment_refuses_paths_outside_the_root(vault, tmp_path):
    assert vault.contains(vault.root / "Index.md")
    assert not vault.contains(tmp_path / "elsewhere.txt")
    assert not vault.has_file("../outside.md")


def test_symlink_escaping_the_root_is_refused(vault, tmp_path):
    outside = tmp_path / "secret.md"
    outside.write_text("secret")
    link = vault.root / "sneaky.md"
    link.symlink_to(outside)
    assert not vault.has_file("sneaky.md")


def test_invalid_utf8_degrades_to_lossy_text(vault):
    bad = vault.root / "latin1.md"
    bad.write_bytes(b"caf\xe9 note")
    note = vault.read_note("latin1.md")
    assert note.lossy
    assert "caf" in note.text
    assert not note.error


def test_oversized_note_is_refused_with_a_named_error(vault, monkeypatch):
    monkeypatch.setattr("obsidian_reader.core.vault.MAX_NOTE_BYTES", 10)
    note = vault.read_note("Index.md")
    assert "too large" in note.error


def test_file_kind_classification():
    assert file_kind("a/b.md") == "note"
    assert file_kind("x.PNG") == "image"
    assert file_kind("x.mp3") == "audio"
    assert file_kind("x.webm") == "video"
    assert file_kind("x.pdf") == "pdf"
    assert file_kind("x.xlsx") == "other"
