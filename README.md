# Obsidian Reader

A read-only Markdown reader for Ubuntu that opens an existing [Obsidian](https://obsidian.md) vault **in place** and renders the Obsidian Markdown that matters for reading — wikilinks, embeds, callouts, frontmatter, tags — without ever writing into the vault, executing plugins or scripts, or touching the network.

It is a fallback reader, not an Obsidian replacement: something dependable to reach for when Obsidian is closed, not installed, or not safe to run against a vault you only want to inspect.

> This project is not affiliated with or endorsed by Obsidian.md / Dynalist Inc. "Obsidian" here names the vault format the reader understands.

## What it does

- Opens a folder as a vault, or a single `.md` file, straight from disk — nothing is imported, copied, or indexed into the vault.
- Renders CommonMark and GFM (tables, task lists, strikethrough, autolinks) plus the Obsidian layer: `[[wikilinks]]`, aliases, heading and block links, `![[embeds]]` with cycle detection, callouts (foldable and nested), `==highlights==`, `%%comments%%` (hidden), inline `#tags`, footnotes (inline included), frontmatter as a collapsible Properties panel, and syntax-highlighted code blocks.
- Resolves links the way Obsidian does: exact relative path first, then vault-root path, then filename match — and when a name is ambiguous it asks instead of guessing.
- Vault-wide filename and full-text search, quick-open, in-note find, back/forward history, outline navigation, session restore, light/dark/system appearance.
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
