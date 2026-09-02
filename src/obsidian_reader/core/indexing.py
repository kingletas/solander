"""Synchronizes the persistent index with the vault: read what changed, keep the rest."""

import os
from dataclasses import dataclass

from .graph import VaultGraph, scan_note
from .store import IndexStore
from .vault import Vault


@dataclass(frozen=True)
class SyncResult:
    """One sync's outcome: the assembled graph and how much work it took."""

    graph: VaultGraph
    scanned: int = 0
    removed: int = 0


def sync_indexes(vault: Vault, store: IndexStore, progress=None) -> SyncResult:
    """Brings the store up to date with the vault and assembles the graph from it.

    Only notes whose (mtime, size) changed are read and re-scanned; everything
    else loads from the store. The graph is always re-assembled in full, so a
    rename or deletion re-resolves every link against the current index.
    """
    cached = store.load_meta()
    stats: dict[str, tuple[float, int]] = {}
    for rel in vault.notes:
        try:
            info = os.stat(vault.root / rel)
            stats[rel] = (info.st_mtime, info.st_size)
        except OSError:
            continue
    gone = [rel for rel in cached if rel not in stats]
    if gone:
        store.remove(gone)
    changed = [rel for rel in stats if cached.get(rel) != stats[rel]]
    scans = store.load_scans()
    for rel in gone:
        scans.pop(rel, None)
    total = len(changed)
    for position, rel in enumerate(changed):
        note = vault.read_note(rel)
        text = note.text if not note.error else ""
        scan = scan_note(text)
        mtime, size = stats[rel]
        store.upsert(rel, mtime, size, text, scan)
        scans[rel] = scan
        if progress is not None:
            progress(position + 1, total)
    store.commit()
    graph = VaultGraph.assemble(vault, scans)
    graph.meta = stats
    return SyncResult(graph=graph, scanned=len(changed), removed=len(gone))
