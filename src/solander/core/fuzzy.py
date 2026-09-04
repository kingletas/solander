"""Fuzzy filename matching for quick-open: matches ranked by kind, then by score.

Scoring alone put `Brie Moffett` above `order-fulfilment-executive-brief` for the
query `brief`, because four letters landing consecutively at the start of a name
outscored the same five letters landing whole, thirty characters in. No weighting
fixes that: a run of the right letters in the wrong word is a different *kind* of
match from the word itself, and a person typing a word means the word. So a match
is classed first and scored second, and no score can promote a scattered match
over a literal one.
"""

import unicodedata
from dataclasses import dataclass

# How a match was made, best first. The class decides the order; the score only
# separates matches of the same class.
WORD_IN_NAME = 0
"""The query is a whole word of the filename."""
INSIDE_NAME = 1
"""The query appears in the filename, but inside a word."""
INSIDE_PATH = 2
"""The query appears in a folder along the way."""
SCATTERED = 3
"""The query's letters are all there, in order, and nothing more can be said."""

GAP_PENALTY = 1
CONSECUTIVE_BONUS = 12
BOUNDARY_BONUS = 10
NAME_START_BONUS = 25
NAME_MATCH_BONUS = 8
_BOUNDARY_CHARS = " -_./([{"


@dataclass(frozen=True)
class FuzzyMatch:
    """One candidate: the path, how the query matched it, and how well."""

    path: str
    score: int
    kind: int = SCATTERED


def fuzzy_match(query: str, path: str) -> int | None:
    """Scores a query as a subsequence of a path, or None when it is not one.

    Consecutive runs, word-boundary hits, and matches inside the filename score
    higher; characters skipped between hits cost a little.
    """
    folded_query = _fold(query)
    folded_path = _fold(path)
    if not folded_query:
        return None
    name_start = folded_path.rfind("/") + 1
    score = 0
    position = 0
    previous_hit = -2
    for char in folded_query:
        found = folded_path.find(char, position)
        if found < 0:
            return None
        gap = found - position
        score -= min(gap, 20) * GAP_PENALTY
        if found == previous_hit + 1:
            score += CONSECUTIVE_BONUS
        if found == 0 or folded_path[found - 1] in _BOUNDARY_CHARS:
            score += BOUNDARY_BONUS
        if found >= name_start:
            score += NAME_MATCH_BONUS
            if found == name_start:
                score += NAME_START_BONUS
        previous_hit = found
        position = found + 1
    return score


def match_kind(query: str, path: str) -> int:
    """Classes how a query matched a path, assuming it matched at all."""
    folded_query = _fold(query)
    folded_path = _fold(path)
    name = folded_path[folded_path.rfind("/") + 1 :]
    at = name.find(folded_query)
    if at >= 0:
        before = name[at - 1] if at else ""
        after = name[at + len(folded_query) : at + len(folded_query) + 1]
        whole = (not before or before in _BOUNDARY_CHARS) and (
            not after or after in _BOUNDARY_CHARS
        )
        return WORD_IN_NAME if whole else INSIDE_NAME
    return INSIDE_PATH if folded_query in folded_path else SCATTERED


def fuzzy_filenames(paths, query: str, limit: int = 200) -> list[FuzzyMatch]:
    """Ranks the paths a query matches: by how it matched, then by score, then by length."""
    words = query.split()
    if not words:
        return []
    matches: list[FuzzyMatch] = []
    for path in paths:
        total = 0
        # Every word has to match, so the weakest one is what the match is worth:
        # a query half of which only scattered has not found the phrase.
        kind = WORD_IN_NAME
        for word in words:
            score = fuzzy_match(word, path)
            if score is None:
                total = None
                break
            total += score
            kind = max(kind, match_kind(word, path))
        if total is not None:
            matches.append(FuzzyMatch(path=path, score=total, kind=kind))
    matches.sort(key=lambda match: (match.kind, -match.score, len(match.path), match.path))
    return matches[:limit]


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()
