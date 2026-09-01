"""Resolves wikilink targets against a vault, refusing to guess when names collide."""

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .vault import NOTE_EXTENSIONS, Vault, file_kind


@dataclass(frozen=True)
class Resolution:
    """The outcome of resolving one link target: found, ambiguous, or missing."""

    kind: str
    path: str = ""
    candidates: list[str] = field(default_factory=list)


def _normalize_relative(base_dir: str, target: str) -> str:
    """Joins a link target onto a note's directory and collapses `.`/`..` inside the vault."""
    joined = PurePosixPath(base_dir) / target if base_dir else PurePosixPath(target)
    parts: list[str] = []
    for part in joined.parts:
        if part == "..":
            if not parts:
                return ""
            parts.pop()
        elif part not in (".", ""):
            parts.append(part)
    return "/".join(parts)


def _try_paths(vault: Vault, candidates: list[str], exists=None) -> str:
    """Returns the first candidate path that names a real file in the vault."""
    check = vault.has_file if exists is None else exists
    for rel in candidates:
        if rel and check(rel):
            return rel
    return ""


def resolve_note(vault: Vault, source: str, target: str, exists=None) -> Resolution:
    """Resolves a wikilink to a note using the path-first, then filename-match order.

    `exists` swaps the per-path filesystem check for a caller-supplied predicate,
    so a bulk pass over the whole vault can resolve against the index snapshot.
    """
    if not target:
        return Resolution(kind="note", path=source)
    base_dir = str(PurePosixPath(source).parent)
    if base_dir == ".":
        base_dir = ""
    with_extensions = [target] if target.casefold().endswith(NOTE_EXTENSIONS) else [
        target,
        f"{target}.md",
        f"{target}.markdown",
    ]
    for candidate in with_extensions:
        found = _try_paths(
            vault,
            [_normalize_relative(base_dir, candidate), _normalize_relative("", candidate)],
            exists,
        )
        if found and file_kind(found) == "note":
            return Resolution(kind="note", path=found)
    name = PurePosixPath(target).name
    matches = vault.notes_named(name)
    if len(matches) == 1:
        return Resolution(kind="note", path=matches[0])
    if len(matches) > 1:
        return Resolution(kind="ambiguous", candidates=sorted(matches))
    return Resolution(kind="missing")


def resolve_attachment(vault: Vault, source: str, target: str, exists=None) -> Resolution:
    """Resolves an embed target to any vault file, checking the attachment folder too."""
    base_dir = str(PurePosixPath(source).parent)
    if base_dir == ".":
        base_dir = ""
    direct = _try_paths(
        vault,
        [
            _normalize_relative(base_dir, target),
            _normalize_relative("", target),
            _normalize_relative(vault.attachment_folder, target) if vault.attachment_folder else "",
        ],
        exists,
    )
    if direct:
        return Resolution(kind=file_kind(direct), path=direct)
    name = PurePosixPath(target).name
    matches = vault.files_named(name)
    if len(matches) == 1:
        return Resolution(kind=file_kind(matches[0]), path=matches[0])
    if len(matches) > 1:
        return Resolution(kind="ambiguous", candidates=sorted(matches))
    return Resolution(kind="missing")


def resolve_embed(vault: Vault, source: str, target: str, exists=None) -> Resolution:
    """Resolves an `![[...]]` target, preferring a note match and falling back to files."""
    if not target:
        return Resolution(kind="note", path=source)
    as_note = resolve_note(vault, source, target, exists)
    if as_note.kind == "note":
        return as_note
    as_file = resolve_attachment(vault, source, target, exists)
    if as_file.kind != "missing":
        return as_file
    return as_note if as_note.kind == "ambiguous" else Resolution(kind="missing")
