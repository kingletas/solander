"""The persistent index store: roundtrips, FTS behavior, and hostile input."""

import sqlite3

from solander.core.graph import NoteScan, RawLink
from solander.core.store import IndexStore, open_index_store


def make_store(tmp_path) -> IndexStore:
    return IndexStore(tmp_path / "index.db")


def test_scan_roundtrip(tmp_path):
    store = make_store(tmp_path)
    scan = NoteScan(links=(RawLink("Alpha", True, "see [[Alpha]]"),), tags=("home", "a/b"))
    store.upsert("Index.md", 1.5, 42, "body text", scan)
    store.commit()
    assert store.load_meta() == {"Index.md": (1.5, 42)}
    assert store.load_scans()["Index.md"] == scan


def test_search_matches_prefixes_and_keeps_original_case(tmp_path):
    store = make_store(tmp_path)
    store.upsert("A.md", 1, 1, "The Ships sail soon.", NoteScan())
    store.upsert("B.md", 1, 1, "Nothing relevant here.", NoteScan())
    store.commit()
    hits = store.search_body(["ship", "soon"], 10)
    assert [rel for rel, _ in hits] == ["A.md"]
    assert "Ships" in hits[0][1]


def test_search_ranks_denser_matches_first(tmp_path):
    store = make_store(tmp_path)
    store.upsert("dense.md", 1, 1, "magento magento magento", NoteScan())
    store.upsert("sparse.md", 1, 1, "magento " + "filler " * 300, NoteScan())
    store.commit()
    hits = store.search_body(["magento"], 10)
    assert hits[0][0] == "dense.md"


def test_search_never_exposes_fts_query_syntax(tmp_path):
    store = make_store(tmp_path)
    store.upsert("A.md", 1, 1, "plain text", NoteScan())
    store.commit()
    for hostile in ['"', 'a" OR "b', "NEAR(", "col:val", "(((", "-x", "^y"]:
        store.search_body([hostile], 10)


def test_remove_drops_note_and_body(tmp_path):
    store = make_store(tmp_path)
    store.upsert("A.md", 1, 1, "findable words", NoteScan())
    store.commit()
    store.remove(["A.md"])
    store.commit()
    assert store.load_meta() == {}
    assert store.search_body(["findable"], 10) == []


def test_schema_version_change_wipes_the_cache(tmp_path):
    path = tmp_path / "index.db"
    store = IndexStore(path)
    store.upsert("A.md", 1, 1, "text", NoteScan())
    store.commit()
    store.close()
    db = sqlite3.connect(path)
    db.execute("PRAGMA user_version = 99")
    db.commit()
    db.close()
    assert IndexStore(path).load_meta() == {}


def test_open_recovers_from_a_corrupted_file(tmp_path):
    path = tmp_path / "index.db"
    path.write_bytes(b"this is not a sqlite database at all" * 10)
    store = open_index_store(path)
    store.upsert("A.md", 1, 1, "text", NoteScan())
    store.commit()
    assert store.load_meta() == {"A.md": (1.0, 1)}
