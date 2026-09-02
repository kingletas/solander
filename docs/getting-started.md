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

This creates a virtualenv against the system Python (so the GI bindings are visible), installs the Python dependencies, and puts an `obsidian-reader` launcher on your `PATH`, along with a desktop entry and icon. `make uninstall` removes all of it.

## 3. First launch — the one-time sandbox step

```bash
obsidian-reader
```

On stock Ubuntu 24.04+ the first launch will most likely **refuse to start and print an AppArmor profile instead**. That is expected: WebKit sandboxes its rendering processes, Ubuntu restricts the user namespaces that sandbox needs, and the fix is a one-time profile granting the permission to this app's interpreter alone — the same mechanism Ubuntu ships for browsers. Install what the launcher printed:

```bash
obsidian-reader 2>&1 | sed -n '/^abi/,/^}/p' | sudo tee /etc/apparmor.d/obsidian-reader
```

```bash
sudo apparmor_parser -r /etc/apparmor.d/obsidian-reader
```

Then launch again. The profile confines nothing (`flags=(unconfined)`); it only lets WebKit's own sandbox turn on. Always start the app through the `obsidian-reader` launcher — it execs the interpreter directly, which is what makes the profile attach.

## 4. Open your vault

```bash
obsidian-reader ~/path/to/your/vault
```

Or use the folder button in the header bar, drag a folder onto the window, or open a single `.md` file. The reader opens the vault **in place** — nothing is imported, and nothing is ever written into it.

The first open of a large vault builds the search and link index in the background — expect roughly 20 seconds for a 10,000-note vault, with progress in the sidebar's status line. The index persists under `~/.cache/obsidian-reader/`, so every later launch is warm: about a second, re-reading only notes that changed. While the reader is open it watches the vault, so anything Obsidian or a sync client writes shows up in the tree, search, and link panels within a few seconds.

## 5. Five things to try first

1. **`Ctrl+P`** — fuzzy quick-open. Type fragments (`scnt` finds "Second Note"); an empty query lists your recent notes.
2. **`Ctrl+Shift+F`** — full-text search, ranked by relevance. Try an operator: `tag:project deadline` or `path:Journal standup`.
3. **Middle-click** a note in the tree or a wikilink in a page — it opens in a new tab. Plain click stays in the current tab.
4. **`Ctrl+M`** — the current note as a mind map of its headings and bullets. `Ctrl+M` again (or the link at the top) brings the markdown back.
5. **`F11`** — reading mode: nothing on screen but the note. `Esc` returns.

`Ctrl+?` shows every shortcut. When you want the rest — Dataview, kanban boards, hidden folders, typography, exports — read the [user guide](user-guide.md).

## Where things live

| What | Where |
|---|---|
| Session, preferences, hidden folders | `~/.config/obsidian-reader/` |
| The per-vault search/link index | `~/.cache/obsidian-reader/` (safe to delete; rebuilt on demand) |
| Your vault | untouched, always |
