"""The persistent index: note scans and an FTS5 body index, stored outside the vault.

The store is a cache of derived data, never a source of truth — corruption or a
schema change means it is deleted and rebuilt from the vault, silently.
"""

import json
import sqlite3
import threading
from pathlib import Path

from .graph import NoteScan, RawLink

SCHEMA_VERSION = 4
SNIPPET_TOKENS = 14


class IndexStore:
    """One SQLite file per vault, safe to touch from the sync thread and the UI."""

    def __init__(self, path: Path | str):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._ensure_schema()

    @property
    def db(self) -> sqlite3.Connection:
        """A per-thread connection; WAL mode lets readers overlap the sync writer."""
        connection = getattr(self._local, "connection", None)
        if connection is None:
            connection = sqlite3.connect(self.path)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            self._local.connection = connection
        return connection

    def _ensure_schema(self) -> None:
        db = self.db
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, SCHEMA_VERSION):
            db.execute("DROP TABLE IF EXISTS notes")
            db.execute("DROP TABLE IF EXISTS fts")
        db.execute(
            "CREATE TABLE IF NOT EXISTS notes ("
            "rel TEXT PRIMARY KEY, mtime REAL, size INTEGER, scan TEXT, fts_rowid INTEGER)"
        )
        db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5("
            "rel UNINDEXED, body, tokenize='unicode61 remove_diacritics 2')"
        )
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        db.commit()

    def load_meta(self) -> dict[str, tuple[float, int]]:
        """Returns every cached note's (mtime, size), the diff key for a sync."""
        rows = self.db.execute("SELECT rel, mtime, size FROM notes").fetchall()
        return {rel: (mtime, size) for rel, mtime, size in rows}

    def load_scans(self) -> dict[str, NoteScan]:
        """Returns every cached scan; a row that fails to decode is simply absent."""
        scans: dict[str, NoteScan] = {}
        for rel, blob in self.db.execute("SELECT rel, scan FROM notes"):
            try:
                data = json.loads(blob)
                scans[rel] = NoteScan(
                    links=tuple(RawLink(t, bool(e), c) for t, e, c in data["links"]),
                    tags=tuple(str(tag) for tag in data["tags"]),
                    props=data.get("props") or {},
                    tasks=tuple(
                        (str(status), str(text)) for status, text in data.get("tasks") or []
                    ),
                )
            except (ValueError, KeyError, TypeError):
                continue
        return scans

    def upsert(self, rel: str, mtime: float, size: int, text: str, scan: NoteScan) -> None:
        """Stores one note's scan and body, replacing any previous row."""
        blob = json.dumps(
            {
                "links": [[link.target, int(link.embed), link.context] for link in scan.links],
                "tags": list(scan.tags),
                "props": scan.props,
                "tasks": [list(task) for task in scan.tasks],
            }
        )
        db = self.db
        # The fts rel column is unindexed, so deletion goes through the stored
        # rowid — a WHERE rel=? there is a full-table scan, O(n²) over a build.
        self._drop_body(rel)
        cursor = db.execute("INSERT INTO fts (rel, body) VALUES (?, ?)", (rel, text))
        db.execute(
            "INSERT OR REPLACE INTO notes (rel, mtime, size, scan, fts_rowid) "
            "VALUES (?, ?, ?, ?, ?)",
            (rel, mtime, size, blob, cursor.lastrowid),
        )

    def remove(self, rels) -> None:
        """Drops cached rows for notes that no longer exist."""
        for rel in rels:
            self._drop_body(rel)
            self.db.execute("DELETE FROM notes WHERE rel = ?", (rel,))

    def _drop_body(self, rel: str) -> None:
        row = self.db.execute("SELECT fts_rowid FROM notes WHERE rel = ?", (rel,)).fetchone()
        if row is not None and row[0] is not None:
            self.db.execute("DELETE FROM fts WHERE rowid = ?", (row[0],))

    def commit(self) -> None:
        self.db.commit()

    def search_body(self, words: list[str], limit: int) -> list[tuple[str, str]]:
        """Returns (rel, snippet) for notes matching every word, best matches first.

        Words become quoted prefix terms, so the query string a user typed can
        never reach FTS5's own query syntax.
        """
        terms = []
        for word in words:
            cleaned = word.replace('"', "")
            if cleaned:
                terms.append(f'"{cleaned}"*')
        if not terms:
            return []
        match = " AND ".join(terms)
        rows = self.db.execute(
            "SELECT rel, snippet(fts, 1, '', '', '…', ?) FROM fts "
            "WHERE fts MATCH ? ORDER BY rank LIMIT ?",
            (SNIPPET_TOKENS, match, limit),
        )
        return [(rel, snippet) for rel, snippet in rows]

    def all_rels(self) -> list[str]:
        """Returns every cached note path, for filter-only queries."""
        return [rel for (rel,) in self.db.execute("SELECT rel FROM notes ORDER BY rel")]

    def close(self) -> None:
        connection = getattr(self._local, "connection", None)
        if connection is not None:
            connection.close()
            self._local.connection = None


def open_index_store(path: Path | str) -> IndexStore:
    """Opens the store, deleting and rebuilding it once if the file is unusable."""
    try:
        return IndexStore(path)
    except sqlite3.DatabaseError:
        Path(path).unlink(missing_ok=True)
        return IndexStore(path)
