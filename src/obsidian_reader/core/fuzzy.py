"""Fuzzy filename matching for quick-open: subsequence scoring, best matches first."""

import unicodedata
from dataclasses import dataclass

GAP_PENALTY = 1
CONSECUTIVE_BONUS = 12
BOUNDARY_BONUS = 10
NAME_START_BONUS = 25
NAME_MATCH_BONUS = 8
_BOUNDARY_CHARS = " -_./([{"


@dataclass(frozen=True)
class FuzzyMatch:
    """One scored candidate: the path and how well the query fits it."""

    path: str
    score: int


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


def fuzzy_filenames(paths, query: str, limit: int = 200) -> list[FuzzyMatch]:
    """Ranks the paths a query fuzzily matches, ties broken by shorter path."""
    words = query.split()
    if not words:
        return []
    matches: list[FuzzyMatch] = []
    for path in paths:
        total = 0
        for word in words:
            score = fuzzy_match(word, path)
            if score is None:
                total = None
                break
            total += score
        if total is not None:
            matches.append(FuzzyMatch(path=path, score=total))
    matches.sort(key=lambda match: (-match.score, len(match.path), match.path))
    return matches[:limit]


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()
