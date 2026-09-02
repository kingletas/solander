"""Application state stored outside every vault: recent vaults, session, preferences."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

MAX_RECENTS = 10
MAX_RECENT_NOTES = 20


def default_state_dir() -> Path:
    """Returns the XDG config directory the reader owns; never a path inside a vault."""
    base = os.environ.get("XDG_CONFIG_HOME", "") or str(Path.home() / ".config")
    return Path(base) / "obsidian-reader"


@dataclass
class SessionState:
    """Everything the reader remembers between launches."""

    recent_vaults: list[str] = field(default_factory=list)
    recent_files: list[str] = field(default_factory=list)
    last_vault: str = ""
    last_note: str = ""
    restore_session: bool = True
    show_hidden: bool = False
    markdown_only: bool = True
    appearance: str = "system"
    theme: str = "atelier"
    zoom: float = 1.0
    window_width: int = 1100
    window_height: int = 760
    sidebar_visible: bool = True
    sidebar_width: int = 280
    open_tabs: list[str] = field(default_factory=list)
    recent_notes: list[str] = field(default_factory=list)
    css_snippets: bool = True
    hidden_folders: dict[str, list[str]] = field(default_factory=dict)
    pinned_notes: dict[str, list[str]] = field(default_factory=dict)
    book_progress: dict[str, str] = field(default_factory=dict)
    reader_font: str = "default"
    line_width: str = "normal"
    line_spacing: str = "normal"
    show_breadcrumb: bool = True
    show_note_meta: bool = True
    show_backlinks_footer: bool = True
    outline_visible: bool = False
    quick_expanded: bool = True


class SessionStore:
    """Loads and saves session state as one JSON file in the app's own directory."""

    def __init__(self, directory: Path | None = None):
        self.directory = directory or default_state_dir()
        self.path = self.directory / "session.json"
        self.state = self._load()

    def _load(self) -> SessionState:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return SessionState()
        if not isinstance(raw, dict):
            return SessionState()
        state = SessionState()
        for key, value in raw.items():
            if hasattr(state, key) and isinstance(value, type(getattr(state, key))):
                setattr(state, key, value)
        return state

    def save(self) -> None:
        """Writes the state atomically; a failed save never corrupts the previous one."""
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(asdict(self.state), indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def remember_vault(self, root: str) -> None:
        """Moves a vault to the top of the recents list and records it as current."""
        recents = [root] + [r for r in self.state.recent_vaults if r != root]
        self.state.recent_vaults = recents[:MAX_RECENTS]
        self.state.last_vault = root

    def remember_file(self, path: str) -> None:
        """Moves a single opened file to the top of the recent-files list."""
        recents = [path] + [r for r in self.state.recent_files if r != path]
        self.state.recent_files = recents[:MAX_RECENTS]

    def remember_note(self, rel: str) -> None:
        """Moves a vault note to the top of the recent-notes list."""
        recents = [rel] + [r for r in self.state.recent_notes if r != rel]
        self.state.recent_notes = recents[:MAX_RECENT_NOTES]
