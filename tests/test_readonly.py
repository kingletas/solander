"""The product's first promise: a full read pass leaves the vault byte-identical."""

import hashlib
from pathlib import Path

from solander.core.indexing import sync_indexes
from solander.core.render import NoteRenderer
from solander.core.store import IndexStore
from solander.core.vault import Vault


def tree_digest(root: Path) -> dict[str, str]:
    digest = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def test_index_search_and_render_write_nothing(vault_dir, tmp_path):
    before = tree_digest(vault_dir)
    vault = Vault.open(vault_dir)
    sync_indexes(vault, IndexStore(tmp_path / "cache" / "index.db"))
    renderer = NoteRenderer(vault)
    for rel in vault.notes:
        renderer.render(rel)
    after = tree_digest(vault_dir)
    assert before == after
