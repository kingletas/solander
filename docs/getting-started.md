# Getting started

Two of the three ways to install take a single command and need no setup afterwards. For the full feature reference, see the [user guide](user-guide.md).

## 1. Install

Pick one. **The Flatpak and the Debian package both skip the sandbox step in section 3** — only a source install needs it.

### The Flatpak — simplest

It needs the GNOME 50 runtime, which is not inside the 3 MB bundle. If you have ever installed anything from Flathub you already have the remote configured; if not, add it first:

```bash
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

Then take the bundle from the [latest release](https://github.com/kingletas/solander/releases/latest) and install it:

```bash
flatpak install --user solander_2.2.3.flatpak
```

The first install also pulls the GNOME runtime — about a gigabyte, once, shared with every other Flatpak you own. Nothing else is required: Flatpak's own sandbox already carries the permission WebKit needs.

### The Debian package — for Ubuntu 24.04+

```bash
sudo apt install ./solander_2.2.3_all.deb
```

`apt` pulls the GObject bindings itself, and the package installs the security profile, so there is nothing to do afterwards.

### From source

You need the system GObject bindings, because the reader is a GTK 4 application rendering through WebKitGTK:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0
```

Optional — for viewing PDFs inside the app (without it, PDFs open in your system viewer):

```bash
sudo apt install gir1.2-poppler-0.18
```

You also need [uv](https://docs.astral.sh/uv/) on your `PATH`. Then, from a clone of this repository:

```bash
make install
```

That creates a virtualenv against the system Python (so the GI bindings are visible), installs the Python dependencies, and puts a `solander` launcher on your `PATH`, along with a desktop entry and icon. `make uninstall` removes all of it.

## 2. Launch it

**Solander** is in your applications grid.

If you installed the Flatpak or the deb, you are done — skip to section 4. A source install has one more step first.

## 3. The one-time sandbox step — source installs only

On stock Ubuntu 24.04+ a source install's first launch shows a **setup window** instead of the reader. That is expected: WebKit sandboxes its rendering processes, Ubuntu restricts the user namespaces that sandbox needs, and the fix is a one-time security profile granting the permission to this app alone — the same mechanism Ubuntu ships for browsers.

The window hands you a single command. **Copy it, paste it into a Terminal, enter your password, then press "I ran it — check again"** — the reader starts on its own. That is the only time a terminal is involved.

(The same flow works headless: launched from a terminal, the app prints the profile and the steps instead. The profile confines nothing — `flags=(unconfined)` plus one `userns` grant — it only lets WebKit's own sandbox turn on. `solander --sandbox-status` reports whether it worked and exits non-zero while anything is still wrong.)

## 4. Open your vault

Use **Open a vault folder…** on the welcome page, drag a folder onto the window, or right-click a folder or `.md` file in your file manager and choose *Open With → Solander*. From a terminal, `solander ~/path/to/vault` does the same — or `flatpak run com.kingletas.Solander ~/path/to/vault` if you installed the Flatpak, which puts no `solander` on your `PATH`. The reader opens the vault **in place** — nothing is imported, and nothing is ever written into it.

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
