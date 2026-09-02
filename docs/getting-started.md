# Getting started

Ten minutes from a fresh Ubuntu machine to reading your vault. For the full feature reference, see the [user guide](user-guide.md).

## 1. Install the system pieces

The reader is a GTK 4 application rendering through WebKitGTK, using the system's GObject bindings:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0
```

Optional — for viewing PDFs inside the app (without it, PDFs open in your system viewer):

```bash
sudo apt install gir1.2-poppler-0.18
```

You also need [uv](https://docs.astral.sh/uv/) on your `PATH`.

## 2. Install the reader

From a clone of this repository:

```bash
make install
```

This creates a virtualenv against the system Python (so the GI bindings are visible), installs the Python dependencies, and puts a `solander` launcher on your `PATH`, along with a desktop entry and icon. `make uninstall` removes all of it.

## 3. First launch — the one-time sandbox step

Launch **Solander** from your applications grid. On stock Ubuntu 24.04+ the first launch shows a **setup window** instead of the reader. That is expected: WebKit sandboxes its rendering processes, Ubuntu restricts the user namespaces that sandbox needs, and the fix is a one-time security profile granting the permission to this app alone — the same mechanism Ubuntu ships for browsers.

The window hands you a single command. **Copy it, paste it into a Terminal, enter your password, then press “I ran it — check again”** — the reader starts on its own. That is the only time a terminal is involved.

(The same flow works headless: launched from a terminal, the app prints the profile and the steps instead. The profile confines nothing — `flags=(unconfined)` plus one `userns` grant — it only lets WebKit's own sandbox turn on.)

## 4. Open your vault

Use **Open a vault folder…** on the welcome page, drag a folder onto the window, or right-click a folder or `.md` file in your file manager and choose *Open With → Solander*. From a terminal, `solander ~/path/to/vault` does the same. The reader opens the vault **in place** — nothing is imported, and nothing is ever written into it.

The first open of a large vault builds the search and link index in the background — expect roughly 20 seconds for a 10,000-note vault, with progress in the sidebar's status line. The index persists under `~/.cache/solander/`, so every later launch is warm: about a second, re-reading only notes that changed. While the reader is open it watches the vault, so anything Obsidian or a sync client writes shows up in the tree, search, and link panels within a few seconds.

## 5. Five things to try first

1. **`Ctrl+P`** — fuzzy quick-open. Type fragments (`scnt` finds "Second Note"); an empty query lists your recent notes.
2. **`Ctrl+Shift+F`** — full-text search, ranked by relevance. Try an operator: `tag:project deadline` or `path:Journal standup`.
3. **Middle-click** a note in the tree or a wikilink in a page — it opens in a new tab. Plain click stays in the current tab.
4. **`Ctrl+M`** — the current note as a mind map of its headings and bullets. `Ctrl+M` again (or the link at the top) brings the markdown back.
5. **`F11`** — reading mode: nothing on screen but the note. `Esc` returns.

`Ctrl+?` shows every shortcut, and **`F1` opens the full user guide inside the app**. When you want the rest — Dataview, kanban boards, hidden folders, typography, exports — it is all in the [user guide](user-guide.md).

## Where things live

| What | Where |
|---|---|
| Session, preferences, hidden folders | `~/.config/solander/` |
| The per-vault search/link index | `~/.cache/solander/` (safe to delete; rebuilt on demand) |
| Your vault | untouched, always |
