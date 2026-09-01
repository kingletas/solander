"""The product's first promise: a full read pass leaves the vault byte-identical."""

import hashlib
from pathlib import Path

from obsidian_reader.core.render import NoteRenderer
from obsidian_reader.core.search import SearchIndex
from obsidian_reader.core.vault import Vault


def tree_digest(root: Path) -> dict[str, str]:
    digest = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def test_index_search_and_render_write_nothing(vault_dir):
    before = tree_digest(vault_dir)
    vault = Vault.open(vault_dir)
    SearchIndex.build(vault)
    renderer = NoteRenderer(vault)
    for rel in vault.notes:
        renderer.render(rel)
    after = tree_digest(vault_dir)
    assert before == after
