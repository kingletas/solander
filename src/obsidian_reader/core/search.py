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
                index.entries[rel] = _fold(note.text)
            if progress is not None:
                progress(position + 1, total)
        index.ready = True
        return index

    def search_content(self, query: str) -> list[SearchHit]:
        """Finds notes containing every word of the query, with a snippet per note."""
        words = [_fold(word) for word in query.split() if word.strip()]
        if not words:
            return []
        hits: list[SearchHit] = []
        for rel, text in self.entries.items():
            positions = [text.find(word) for word in words]
            if any(position < 0 for position in positions):
                continue
            hits.append(SearchHit(path=rel, snippet=_snippet(text, min(positions), words[0])))
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


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def _snippet(text: str, position: int, word: str) -> str:
    start = max(0, position - SNIPPET_RADIUS)
    end = min(len(text), position + len(word) + SNIPPET_RADIUS)
    fragment = re.sub(r"\s+", " ", text[start:end]).strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{fragment}{suffix}"
