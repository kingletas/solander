"""The incremental sync: cache hits, change detection, and the zero-write promise."""

import hashlib
import os

from solander.core.indexing import sync_indexes
from solander.core.store import IndexStore


def tree_hash(root) -> str:
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            digest.update(path.encode())
            with open(path, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()


def test_first_sync_scans_everything_and_builds_the_graph(vault, tmp_path):
    store = IndexStore(tmp_path / "index.db")
    result = sync_indexes(vault, store)
    assert result.scanned == len(vault.notes)
    assert result.graph.ready
    assert "Projects/Alpha.md" in result.graph.backlinks


def test_second_sync_scans_nothing(vault, tmp_path):
    store = IndexStore(tmp_path / "index.db")
    sync_indexes(vault, store)
    result = sync_indexes(vault, store)
    assert result.scanned == 0
    assert "Projects/Alpha.md" in result.graph.backlinks


def test_a_changed_note_is_rescanned_and_the_graph_follows(vault, vault_dir, tmp_path):
    store = IndexStore(tmp_path / "index.db")
    sync_indexes(vault, store)
    target = vault_dir / "Personal" / "Cycle A.md"
    target.write_text("Now links to [[Projects/Alpha]] instead.\n")
    os.utime(target, (1e9, 1e9))
    vault.reindex()
    result = sync_indexes(vault, store)
    assert result.scanned == 1
    sources = [m.source for m in result.graph.backlinks["Projects/Alpha.md"]]
    assert "Personal/Cycle A.md" in sources


def test_a_deleted_note_leaves_the_graph_and_the_store(vault, vault_dir, tmp_path):
    store = IndexStore(tmp_path / "index.db")
    sync_indexes(vault, store)
    (vault_dir / "Personal" / "Cycle A.md").unlink()
    vault.reindex()
    result = sync_indexes(vault, store)
    assert result.removed == 1
    assert all(
        m.source != "Personal/Cycle A.md"
        for m in result.graph.backlinks.get("Personal/Cycle B.md", [])
    )
    assert "Personal/Cycle A.md" not in store.load_meta()


def test_a_new_note_resolves_links_in_unchanged_notes(vault, vault_dir, tmp_path):
    store = IndexStore(tmp_path / "index.db")
    first = sync_indexes(vault, store)
    kinds = {link.target: link.kind for link in first.graph.outgoing["Index.md"]}
    assert kinds["Nowhere To Be Found"] == "missing"
    (vault_dir / "Nowhere To Be Found.md").write_text("# Found now\n")
    vault.reindex()
    result = sync_indexes(vault, store)
    kinds = {link.target: link.kind for link in result.graph.outgoing["Index.md"]}
    assert kinds["Nowhere To Be Found"] == "note"


def test_sync_writes_nothing_into_the_vault(vault, vault_dir, tmp_path):
    before = tree_hash(vault_dir)
    store = IndexStore(tmp_path / "cache" / "index.db")
    sync_indexes(vault, store)
    sync_indexes(vault, store)
    assert tree_hash(vault_dir) == before
