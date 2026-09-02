"""The vault model: enumerates notes in place and never writes below the root."""

import json
import os
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .links import normalize_name

NOTE_EXTENSIONS = (".md", ".markdown")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".avif")
AUDIO_EXTENSIONS = (".mp3", ".ogg", ".oga", ".wav", ".flac", ".m4a", ".opus")
VIDEO_EXTENSIONS = (".mp4", ".webm", ".mkv", ".ogv", ".mov")

# The single knob a deployment may want: notes larger than this are refused as
# text, because a multi-hundred-megabyte "note" is not one and would stall the UI.
MAX_NOTE_BYTES = int(os.environ.get("READER_MAX_NOTE_BYTES", str(10 * 1024 * 1024)))


@dataclass(frozen=True)
class NoteText:
    """The decoded text of a note, with the problem named when decoding degraded."""

    text: str = ""
    error: str = ""
    lossy: bool = False


@dataclass
class Vault:
    """A vault root and the read-only indexes built over it."""

    root: Path
    notes: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    _notes_by_name: dict[str, list[str]] = field(default_factory=dict)
    _files_by_name: dict[str, list[str]] = field(default_factory=dict)
    attachment_folder: str = ""
    ignore_filters: list[str] = field(default_factory=list)

    @classmethod
    def open(cls, root: Path) -> "Vault":
        """Builds a vault over a directory, indexing every non-hidden file below it."""
        vault = cls(root=root.resolve())
        vault.reindex()
        vault.attachment_folder = vault._read_attachment_folder()
        vault.ignore_filters = vault._read_ignore_filters()
        return vault

    def reindex(self) -> None:
        """Rebuilds the note and file indexes from the current directory contents."""
        notes: list[str] = []
        files: list[str] = []
        by_name: dict[str, list[str]] = {}
        files_by_name: dict[str, list[str]] = {}
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            rel_dir = Path(dirpath).relative_to(self.root)
            for filename in sorted(filenames):
                if filename.startswith("."):
                    continue
                rel = str(rel_dir / filename) if str(rel_dir) != "." else filename
                files.append(rel)
                key = unicodedata.normalize("NFC", filename).casefold()
                files_by_name.setdefault(key, []).append(rel)
                if filename.casefold().endswith(NOTE_EXTENSIONS):
                    notes.append(rel)
                    by_name.setdefault(normalize_name(filename), []).append(rel)
        self.notes = notes
        self.files = files
        self._notes_by_name = by_name
        self._files_by_name = files_by_name

    def contains(self, path: Path) -> bool:
        """Reports whether a resolved path stays inside the vault root."""
        try:
            path.resolve().relative_to(self.root)
        except ValueError:
            return False
        return True

    def has_file(self, rel: str) -> bool:
        """Reports whether a vault-relative path names an existing, contained file."""
        candidate = self.root / rel
        return self.contains(candidate) and candidate.is_file()

    def notes_named(self, name: str) -> list[str]:
        """Returns every note whose filename stem matches, case- and accent-insensitively."""
        return list(self._notes_by_name.get(normalize_name(name), []))

    def files_named(self, name: str) -> list[str]:
        """Returns every file whose full name matches, case- and accent-insensitively."""
        key = unicodedata.normalize("NFC", name).casefold()
        return list(self._files_by_name.get(key, []))

    def read_note(self, rel: str) -> NoteText:
        """Reads a note as UTF-8, degrading to a lossy decode with the failure named."""
        path = self.root / rel
        if not self.contains(path):
            return NoteText(error=f"{rel} is outside the vault")
        try:
            size = path.stat().st_size
        except OSError as error:
            return NoteText(error=f"Cannot read {rel}: {error.strerror or error}")
        if size > MAX_NOTE_BYTES:
            return NoteText(error=f"{rel} is {size:,} bytes — too large to open as a note")
        try:
            data = path.read_bytes()
        except OSError as error:
            return NoteText(error=f"Cannot read {rel}: {error.strerror or error}")
        try:
            return NoteText(text=data.decode("utf-8"))
        except UnicodeDecodeError:
            return NoteText(text=data.decode("utf-8", errors="replace"), lossy=True)

    def _read_attachment_folder(self) -> str:
        """Reads the configured attachment folder out of `.obsidian/app.json`, read-only."""
        config = self.root / ".obsidian" / "app.json"
        try:
            parsed = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ""
        folder = parsed.get("attachmentFolderPath", "") if isinstance(parsed, dict) else ""
        if not isinstance(folder, str) or folder.startswith("."):
            return ""
        return folder.strip("/")


    def _read_ignore_filters(self) -> list[str]:
        """Reads Obsidian's own excluded-files list out of `.obsidian/app.json`."""
        config = self.root / ".obsidian" / "app.json"
        try:
            parsed = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        filters = parsed.get("userIgnoreFilters") if isinstance(parsed, dict) else None
        if not isinstance(filters, list):
            return []
        return [
            entry.rstrip("/")
            for entry in filters
            if isinstance(entry, str) and entry.strip("/") and not entry.startswith(".")
        ]


def hidden_under(rel: str, hidden) -> bool:
    """Reports whether a vault-relative path sits inside any hidden folder."""
    for folder in hidden:
        if rel == folder or rel.startswith(f"{folder}/"):
            return True
    return False


def file_kind(rel: str) -> str:
    """Classifies a vault file as note, image, audio, video, pdf, or other."""
    lower = rel.casefold()
    if lower.endswith(NOTE_EXTENSIONS):
        return "note"
    if lower.endswith(IMAGE_EXTENSIONS):
        return "image"
    if lower.endswith(AUDIO_EXTENSIONS):
        return "audio"
    if lower.endswith(VIDEO_EXTENSIONS):
        return "video"
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".canvas"):
        return "canvas"
    if lower.endswith(".base"):
        return "base"
    return "other"
