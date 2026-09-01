"""In-memory filename and full-text search over a vault, built off the UI thread."""

import re
import unicodedata
from dataclasses import dataclass, field

from .vault import Vault

MAX_RESULTS = 200
SNIPPET_RADIUS = 60


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


@dataclass
class SearchIndex:
    """Lowercased note contents held in memory; the vault itself is never written."""

    entries: dict[str, str] = field(default_factory=dict)
    ready: bool = False

    @classmethod
    def build(cls, vault: Vault, progress=None) -> "SearchIndex":
        """Reads every note once and keeps a fold-cased copy for scanning."""
        index = cls()
        total = len(vault.notes)
        for position, rel in enumerate(vault.notes):
            note = vault.read_note(rel)
            if not note.error:
                index.add(rel, note.text)
            if progress is not None:
                progress(position + 1, total)
        index.ready = True
        return index

    def add(self, rel: str, text: str) -> None:
        """Indexes one note's text under its vault-relative path."""
        self.entries[rel] = _fold(text)

    def search_content(
        self, query: str, note_tags: dict[str, set[str]] | None = None
    ) -> list[SearchHit]:
        """Finds notes matching every word and filter, with a snippet per note."""
        parsed = parse_query(query)
        if parsed.empty:
            return []
        hits: list[SearchHit] = []
        for rel, text in self.entries.items():
            folded_rel = _fold(rel)
            if any(term not in folded_rel for term in parsed.paths):
                continue
            name = folded_rel.rsplit("/", 1)[-1]
            if any(term not in name for term in parsed.files):
                continue
            if parsed.tags and not _tags_match(parsed.tags, (note_tags or {}).get(rel, set())):
                continue
            positions = [text.find(word) for word in parsed.words]
            if any(position < 0 for position in positions):
                continue
            snippet = _snippet(text, min(positions), parsed.words[0]) if parsed.words else ""
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


def _snippet(text: str, position: int, word: str) -> str:
    start = max(0, position - SNIPPET_RADIUS)
    end = min(len(text), position + len(word) + SNIPPET_RADIUS)
    fragment = re.sub(r"\s+", " ", text[start:end]).strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{fragment}{suffix}"
