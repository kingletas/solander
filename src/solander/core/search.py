"""Filename and full-text search: query parsing, operators, and the FTS-backed service."""

import re
import unicodedata
from dataclasses import dataclass

from .fuzzy import fuzzy_filenames
from .store import IndexStore
from .vault import Vault, hidden_under

MAX_RESULTS = 200

# Obsidian's property operator: `[status]` or `[project:Garden Shed]`. It is
# lifted out before the query is split into words, since a value may hold spaces.
_PROPERTY = re.compile(r"\[([^\[\]:]+)(?::([^\[\]]*))?\]")


@dataclass(frozen=True)
class SearchHit:
    """One search result: the note, and the snippet that matched."""

    path: str
    snippet: str = ""


@dataclass(frozen=True)
class Query:
    """A parsed search: plain words plus `path:`, `file:`, `tag:` and `[property]` filters.

    Each property filter is a name and the value it must contain, or None when
    having the property at all is enough.
    """

    words: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    properties: tuple[tuple[str, str | None], ...] = ()

    @property
    def empty(self) -> bool:
        return not (self.words or self.paths or self.files or self.tags or self.properties)


def parse_query(text: str) -> Query:
    """Splits a query into words and operator filters; unknown operators stay words."""
    properties: list[tuple[str, str | None]] = []

    def lift(match: re.Match) -> str:
        name, value = match.group(1).strip(), (match.group(2) or "").strip()
        if not name:
            return match.group(0)
        properties.append((_fold(name), _fold(value) if value else None))
        return " "

    text = _PROPERTY.sub(lift, text)
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
        properties=tuple(properties),
    )


class VaultSearch:
    """Full-text search over the persistent index, ranked by FTS5's own scoring."""

    def __init__(self, store: IndexStore):
        self.store = store
        self.ready = False

    def search_content(
        self,
        query: str,
        note_tags: dict[str, set[str]] | None = None,
        note_props: dict[str, dict] | None = None,
    ) -> list[SearchHit]:
        """Finds notes matching every word and filter, best matches first."""
        parsed = parse_query(query)
        if parsed.empty:
            return []
        filtered = bool(parsed.paths or parsed.files or parsed.tags or parsed.properties)
        if parsed.words and not filtered:
            candidates = self.store.search_body(list(parsed.words), MAX_RESULTS)
        elif parsed.words:
            # Filters run outside the index, so every match is filtered first and only the
            # notes kept are given snippets; a cap before the filter would lose what it wants.
            candidates = [(rel, "") for rel in self.store.match_rels(list(parsed.words))]
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
            props = (note_props or {}).get(rel) or {}
            if parsed.properties and not _properties_match(parsed.properties, props):
                continue
            hits.append(SearchHit(path=rel, snippet=snippet))
            if len(hits) >= MAX_RESULTS:
                break
        if parsed.words and filtered:
            snippets = self.store.snippets_for(list(parsed.words), [hit.path for hit in hits])
            hits = [SearchHit(path=hit.path, snippet=snippets.get(hit.path, "")) for hit in hits]
        return hits


def search_filenames(vault: Vault, query: str) -> list[SearchHit]:
    """Finds notes whose path fuzzily matches the query, best matches first."""
    matches = fuzzy_filenames(vault.notes, query, limit=MAX_RESULTS)
    return [SearchHit(path=match.path) for match in matches]


def demote(hits: list[SearchHit], excluded) -> list[SearchHit]:
    """Moves hits under an excluded folder behind the rest, order otherwise kept.

    Obsidian de-emphasises the folders named in its excluded-files setting rather
    than hiding them, so a note only an archive holds is still the answer when
    nothing else matches. Relevance is what the index scored; which folders are
    history is something only the vault can say.
    """
    if not excluded:
        return list(hits)
    kept = [hit for hit in hits if not hidden_under(hit.path, excluded)]
    behind = [hit for hit in hits if hidden_under(hit.path, excluded)]
    return kept + behind


def _tags_match(terms: tuple[str, ...], tags: set[str]) -> bool:
    """Reports whether every tag term matches a note tag exactly or as a nested parent."""
    return all(
        any(tag == term or tag.startswith(f"{term}/") for tag in tags) for term in terms
    )


def _properties_match(terms: tuple[tuple[str, str | None], ...], props: dict) -> bool:
    """Reports whether a note's frontmatter has every property, each holding its value.

    Names are compared case-insensitively. A value matches when it appears in the
    property's text, or in any item of a list.
    """
    folded = {_fold(str(key)): value for key, value in props.items()}
    for name, wanted in terms:
        if name not in folded:
            return False
        if wanted is None:
            continue
        value = folded[name]
        items = value if isinstance(value, list) else [value]
        if not any(wanted in _fold(str(item)) for item in items if item is not None):
            return False
    return True


def _fold(text: str) -> str:
    """Case and accents removed, as the index removes them, so filters match the same way."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()
