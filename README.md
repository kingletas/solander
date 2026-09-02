# Obsidian Reader

A read-only Markdown reader for Ubuntu that opens an existing [Obsidian](https://obsidian.md) vault **in place** and renders the Obsidian Markdown that matters for reading — wikilinks, embeds, callouts, frontmatter, tags — without ever writing into the vault, executing plugins or scripts, or touching the network.

It is a fallback reader, not an Obsidian replacement: something dependable to reach for when Obsidian is closed, not installed, or not safe to run against a vault you only want to inspect.

> This project is not affiliated with or endorsed by Obsidian.md / Dynalist Inc. "Obsidian" here names the vault format the reader understands.

## What it does

The full walkthrough is the **[user guide](docs/user-guide.md)**; installation is **[getting started](docs/getting-started.md)**. In summary:

- **Renders the whole vault, not just the markdown.** CommonMark/GFM plus the Obsidian layer — wikilinks with Obsidian's own resolution order, embeds, callouts, highlights, comments, tags, footnotes, frontmatter properties, syntax-highlighted code — and TeX math as native MathML, `.canvas` pages, kanban boards as boards, Excalidraw drawings as SVG, `.base` table views, and **Dataview queries and inline expressions evaluated in pure Python**, live against the index. Anything unsupported degrades to labeled source with the reason.
- **Finds things like a launcher.** Fuzzy quick-open, relevance-ranked full-text search with `path:`/`file:`/`tag:` operators and highlighted hits, backlinks with context, a tag browser, the vault's bookmarks, a local graph, and hover previews.
- **Stays current and starts warm.** The vault is watched — outside edits appear in seconds — and the index persists per vault, so a 10,000-note vault opens in about a second after its first build.
- **Reads comfortably.** Tabs, a mind-map view of any note, reading (zen) mode, typography controls, light/dark, the vault's own CSS snippets (sanitized), folder hiding, and PDF export through a proper print stylesheet — plus an in-app PDF viewer when Poppler's bindings are present.

## What it will never do

- **Write into the vault.** No caches, indexes, locks, conflict files, or thumbnails. All application state lives under `~/.config/obsidian-reader/` and `~/.cache/obsidian-reader/`.
- **Execute anything from a note.** JavaScript is disabled in the rendering surface; raw HTML in notes is escaped, and the generated HTML passes through an allowlist sanitizer before display. Templater and `dataviewjs` render as labeled inert source.
- **Touch the network.** Remote images, scripts, stylesheets, and fonts are blocked; `http`/`https` links open in your system browser, and every other URI scheme is refused.

## Install

Requires Ubuntu 24.04+ (GTK 4, libadwaita 1.5+, WebKitGTK 6.0) with the system GObject bindings:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0
```

Optional, for the embedded PDF preview (PDFs open externally without it):

```bash
sudo apt install gir1.2-poppler-0.18
```

Then, with [uv](https://docs.astral.sh/uv/) installed:

```bash
make install
```

That creates the virtualenv against the system Python (so the GI bindings are visible), installs the dependencies, and puts an `obsidian-reader` launcher on your `PATH`. `make help` lists everything else.

## Run

```bash
obsidian-reader ~/path/to/vault      # open a folder as a vault
obsidian-reader note.md              # open a single note
obsidian-reader                      # reopen the last session
```

A second launch hands its path to the running instance instead of racing it for state.

## Documentation

- **[Getting started](docs/getting-started.md)** — install, the one-time sandbox step, first vault.
- **[User guide](docs/user-guide.md)** — every feature, the Dataview surface, shortcuts, configuration, troubleshooting.
- **[SECURITY.md](SECURITY.md)** — the threat model and reporting route.
- **[CHANGELOG.md](CHANGELOG.md)** — release history.

## The sandbox and Ubuntu's user-namespace policy

WebKitGTK wraps its rendering processes in a bubblewrap sandbox, and that sandbox needs to create an unprivileged user namespace. Ubuntu 24.04+ restricts those by default (`kernel.apparmor_restrict_unprivileged_userns=1`), so on a stock system the app would abort with `bwrap: setting up uid map: Permission denied`. The launcher detects this before WebKit crashes and prints the fix.

The fix is a one-time AppArmor profile that grants the permission to this app's interpreter alone (`make install` gives the venv a private interpreter copy so the profile names nothing else). Run `obsidian-reader` once — it prints the profile rendered for your installation — then install it:

```bash
obsidian-reader 2>&1 | sed -n '/^abi/,/^}/p' | sudo tee /etc/apparmor.d/obsidian-reader
```

```bash
sudo apparmor_parser -r /etc/apparmor.d/obsidian-reader
```

Then start the app again. This is the same mechanism Ubuntu itself ships for browsers: the profile is `flags=(unconfined)` — it confines nothing — plus a single `userns,` grant, and it keeps WebKit's sandbox *on*, which is strictly better than the workaround of disabling user-namespace restrictions system-wide.

One subtlety the launcher handles for you: AppArmor attaches the profile by interpreter path, and a `#!` shebang launch (such as running the venv's console script directly) bypasses attachment. The `obsidian-reader` launcher execs the interpreter directly for exactly this reason — start the app through it.

## Development

```bash
make check    # ruff + the test suite — everything a commit has to pass
make test     # test suite only
make run      # run from the working tree
```

The core (vault model, link resolution, Markdown transforms, sanitizer, search) is pure Python with no GTK dependency, and the test suite covers it directly — including a zero-write test that hashes a fixture vault before and after a full index-and-render pass. The GTK/WebKit layer stays thin and is exercised by running the app.

## Security model

The vault is treated as attacker-controlled input. The trust boundary is the sanitizer: everything upstream of it (parsing, transforms, link resolution) handles untrusted text, and nothing downstream receives unsanitized markup. On top of that, the WebKit surface runs with JavaScript disabled (and refuses to start if it cannot be), vault assets are served through a `vault:` URI scheme handler that refuses any path resolving outside the vault root, and the navigation policy blocks every load that is not an internal page, a vault asset, or a user-initiated external link. Resource use is bounded too: note size, frontmatter size, embed depth, and embeds per page are capped, and YAML aliases in frontmatter are refused — each bound proven against a payload that previously froze the renderer. See [SECURITY.md](SECURITY.md) for the model and the reporting route.

## License

MIT — see [LICENSE](LICENSE).
