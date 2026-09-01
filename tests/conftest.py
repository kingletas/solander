"""Shared fixture: a small on-disk vault exercising the syntax the reader supports."""

import pytest

from obsidian_reader.core.vault import Vault

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
)


@pytest.fixture
def vault_dir(tmp_path):
    root = tmp_path / "vault"
    (root / "Projects").mkdir(parents=True)
    (root / "Personal").mkdir()
    (root / "assets").mkdir()
    (root / ".obsidian").mkdir()
    (root / ".obsidian" / "app.json").write_text('{"attachmentFolderPath": "assets"}')

    (root / "Index.md").write_text(
        "---\n"
        "title: Index\n"
        "tags:\n  - home\n"
        "---\n"
        "# Welcome\n\n"
        "See [[Projects/Alpha]] and [[Alpha|the alias]] and [[Alpha#Timeline]].\n\n"
        "A ==highlight== and a #project/tag here. %%hidden inline%%\n\n"
        "%%\na hidden block\nspanning lines\n%%\n\n"
        "- [x] done task\n"
        "- [ ] open task\n"
        "- [-] cancelled task\n"
        "- [/] running task\n\n"
        "> [!warning]- Folded warning\n"
        "> Careful with **this**.\n\n"
        "> [!note]\n"
        "> Outer callout.\n"
        "> > [!tip] Inner\n"
        "> > Nested callout.\n\n"
        "![[diagram.png|300]]\n\n"
        "![[Projects/Alpha#Timeline]]\n\n"
        "A missing link: [[Nowhere To Be Found]].\n\n"
        "An ambiguous link: [[Meeting Notes]].\n\n"
        "```dataview\nTABLE file.mtime\n```\n\n"
        "```python\nprint('hi')\n```\n"
    )
    (root / "Projects" / "Alpha.md").write_text(
        "# Alpha\n\nIntro paragraph. ^intro\n\n## Timeline\n\nShips soon.\n\n## Notes\n\nMore.\n"
    )
    (root / "Projects" / "Meeting Notes.md").write_text("# Work meeting\n")
    (root / "Personal" / "Meeting Notes.md").write_text("# Personal meeting\n")
    (root / "Personal" / "Cycle A.md").write_text("![[Cycle B]]\n")
    (root / "Personal" / "Cycle B.md").write_text("![[Cycle A]]\n")
    (root / "assets" / "diagram.png").write_bytes(PNG_BYTES)
    return root


@pytest.fixture
def vault(vault_dir):
    return Vault.open(vault_dir)
