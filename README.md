# Obsidian Reader

A read-only Markdown reader for Ubuntu that opens an existing [Obsidian](https://obsidian.md) vault **in place** and renders the Obsidian Markdown that matters for reading — wikilinks, embeds, callouts, frontmatter, tags — without ever writing into the vault, executing plugins or scripts, or touching the network.

It is a fallback reader, not an Obsidian replacement: something dependable to reach for when Obsidian is closed, not installed, or not safe to run against a vault you only want to inspect.

> This project is not affiliated with or endorsed by Obsidian.md / Dynalist Inc. "Obsidian" here names the vault format the reader understands.

## What it does

- Opens a folder as a vault, or a single `.md` file, straight from disk — nothing is imported, copied, or indexed into the vault.
- Renders CommonMark and GFM (tables, task lists, strikethrough, autolinks) plus the Obsidian layer: `[[wikilinks]]`, aliases, heading and block links, `![[embeds]]` with cycle detection, callouts (foldable and nested), `==highlights==`, `%%comments%%` (hidden), inline `#tags`, footnotes (inline included), frontmatter as a collapsible Properties panel, and syntax-highlighted code blocks.
- Resolves links the way Obsidian does: exact relative path first, then vault-root path, then filename match — and when a name is ambiguous it asks instead of guessing.
- Vault-wide filename and full-text search — relevance-ranked, with `path:`, `file:`, and `tag:` operators — plus quick-open, in-note find, back/forward history, outline navigation, session restore, light/dark/system appearance.
- Stays current: the vault is watched, so a note created or edited by anything else (Obsidian, a sync client, a script) shows up in the tree, the search index, and the link graph within seconds — no reload step.
- Remembers the index between launches: a per-vault cache under `~/.cache/obsidian-reader/` means a warm start indexes in about a second even for a 10,000-note vault (the cache costs disk roughly proportional to the vault's text; "Clear Index Cache" in the menu removes and rebuilds it).
- A link graph built at open: a Links pane showing every note that links to the current one (with the line of context) and its outgoing links, a Tags pane listing every inline and frontmatter tag with counts, and a Bookmarks pane reading the vault's own `.obsidian/bookmarks.json` — read-only, like everything else.
- Hover previews: rest the pointer on a wikilink and a popover shows the opening of the target note.
- A reading (zen) mode — `F11` strips every piece of chrome, `Esc` brings it back — and PDF export (`Ctrl+Shift+E`) of the current rendered note, which refuses to write inside the vault.
- Tabs: middle-click or `Ctrl+click` a note or wikilink to open it in a new tab (`Ctrl+T`/`Ctrl+W` to open and close); a plain click opens in the current tab. The sidebar drags to any width, and both survive a restart.
- Reads `.obsidian/app.json` (read-only) to honor the vault's attachment-folder setting.

## What it will never do

- **Write into the vault.** No caches, indexes, locks, conflict files, or thumbnails. All application state lives under `~/.config/obsidian-reader/` and `~/.cache/obsidian-reader/`.
- **Execute anything from a note.** JavaScript is disabled in the rendering surface; raw HTML in notes is escaped, and the generated HTML passes through an allowlist sanitizer before display. Dataview, Templater, and plugin syntax render as labeled inert source.
- **Touch the network.** Remote images, scripts, stylesheets, and fonts are blocked; `http`/`https` links open in your system browser, and every other URI scheme is refused.

## Install

Requires Ubuntu 24.04+ (GTK 4, libadwaita 1.5+, WebKitGTK 6.0) with the system GObject bindings:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0
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
