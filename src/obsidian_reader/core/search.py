"""Filename and full-text search: query parsing, operators, and the FTS-backed service."""

import unicodedata
from dataclasses import dataclass

from .store import IndexStore
from .vault import Vault

MAX_RESULTS = 200


@dataclass(frozen=True)
class SearchHit:
    """One search result: the note, and the snippet that matched."""

    path: str
    snippet: str = ""


@dataclass(frozen=True)
class Query:
    """A parsed search: plain words plus `path:`, `file:`, and `tag:` filters."""

    words: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not (self.words or self.paths or self.files or self.tags)


def parse_query(text: str) -> Query:
    """Splits a query into words and operator filters; unknown operators stay words."""
    words: list[str] = []
    filters: dict[str, list[str]] = {"path": [], "file": [], "tag": []}
    for token in text.split():
        operator, sep, value = token.partition(":")
        if sep and operator.casefold() in filters and value:
            filters[operator.casefold()].append(_fold(value.lstrip("#")))
        else:
            words.append(_fold(token))
    return Query(
        words=tuple(words),
        paths=tuple(filters["path"]),
        files=tuple(filters["file"]),
        tags=tuple(filters["tag"]),
    )


class VaultSearch:
    """Full-text search over the persistent index, ranked by FTS5's own scoring."""

    def __init__(self, store: IndexStore):
        self.store = store
        self.ready = False

    def search_content(
        self, query: str, note_tags: dict[str, set[str]] | None = None
    ) -> list[SearchHit]:
        """Finds notes matching every word and filter, best matches first."""
        parsed = parse_query(query)
        if parsed.empty:
            return []
        if parsed.words:
            candidates = self.store.search_body(list(parsed.words), MAX_RESULTS * 5)
        else:
            candidates = [(rel, "") for rel in self.store.all_rels()]
        hits: list[SearchHit] = []
        for rel, snippet in candidates:
            folded_rel = _fold(rel)
            if any(term not in folded_rel for term in parsed.paths):
                continue
            name = folded_rel.rsplit("/", 1)[-1]
            if any(term not in name for term in parsed.files):
                continue
            if parsed.tags and not _tags_match(parsed.tags, (note_tags or {}).get(rel, set())):
                continue
            hits.append(SearchHit(path=rel, snippet=snippet))
            if len(hits) >= MAX_RESULTS:
                break
        return hits


def search_filenames(vault: Vault, query: str) -> list[SearchHit]:
    """Finds notes whose path contains every word of the query, best matches first."""
    words = [_fold(word) for word in query.split() if word.strip()]
    if not words:
        return []
    scored: list[tuple[int, str]] = []
    for rel in vault.notes:
        folded = _fold(rel)
        if all(word in folded for word in words):
            name = _fold(rel.rsplit("/", 1)[-1])
            rank = 0 if name.startswith(words[0]) else (1 if words[0] in name else 2)
            scored.append((rank, rel))
    scored.sort(key=lambda pair: (pair[0], len(pair[1]), pair[1]))
    return [SearchHit(path=rel) for _, rel in scored[:MAX_RESULTS]]


def _tags_match(terms: tuple[str, ...], tags: set[str]) -> bool:
    """Reports whether every tag term matches a note tag exactly or as a nested parent."""
    return all(
        any(tag == term or tag.startswith(f"{term}/") for tag in tags) for term in terms
    )


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()
