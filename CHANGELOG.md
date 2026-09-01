# Changelog

## 0.4.0 — 2026-09-01

- A vault-wide link graph, built in the background alongside the search index in one pass over the notes. It powers three new sidebar pages beside Files and Search:
  - **Links** — every note that links to the current one ("linked mentions"), each with the line of context around the mention, plus the note's outgoing links with unresolved and ambiguous targets named as such. Links inside fenced code, inline code, and comments do not count; media embeds stay out of the graph.
  - **Tags** — every tag in the vault (inline and frontmatter), with counts and a filter box. Activating a tag runs a `tag:` search.
  - **Bookmarks** — the vault's own `.obsidian/bookmarks.json`, read-only, groups flattened into headers; entries pointing at files that no longer exist are dropped.
- Search operators: `path:`, `file:`, and `tag:` narrow a full-text search (`tag:` matches nested children, so `tag:project` finds `project/tag`). A query of filters alone works too.
- Hover previews: rest the pointer on a wikilink for a moment and a popover shows the opening of the target note, rendered through the same sanitized pipeline with its own tight embed budget. The preview surface takes no input, so a click always lands on the page under it.
- The mention list per note and the bookmark count are bounded (`READER_MAX_MENTIONS_PER_TARGET`, `READER_MAX_BOOKMARKS`), so hostile input cannot grow either without limit.
- The GUI smoke run now refuses to pass when zero checks ran: it previously forwarded its activation to an already-running reader instance and reported an empty failure list as a pass. It runs non-unique now, and an empty run is a failure.

## 0.3.0 — 2026-09-01

- Tabs: `Ctrl+T` opens a new tab, `Ctrl+W` closes one (the last tab shows the welcome page instead of closing the window), and middle-click or `Ctrl+click` on a file-tree note or an in-note wikilink opens it in a new tab. A plain click still opens in the current tab. Every tab has its own history and outline; open tabs are restored with the session. All tabs share one WebKit context, so the process cost of a tab is a web view, not a browser.
- The sidebar is now resizable by dragging the divider, and its width persists across sessions. Deep folder trees no longer squeeze the note names into ellipses.
- A single click on a folder now expands or collapses it; notes likewise open on single click.

## 0.2.2 — 2026-09-01

- The AppArmor profile from 0.2.1 loaded but never attached, so the app still refused to start: AppArmor attaches a profile by interpreter path, and launching through the venv console script's `#!` shebang bypasses that (proven by direct test — the same interpreter attaches when exec'd directly or via its symlink, and not via a shebang). The launcher now execs the venv interpreter directly, which attaches the profile and starts WebKit's sandbox correctly.
- When the sandbox probe fails but the profile is already installed and unattached, the preflight now explains the shebang trap and points at the launcher, instead of telling you to install the profile you already have.

## 0.2.1 — 2026-09-01

- On stock Ubuntu 24.04+ the app could not start from a normal terminal: the kernel's unprivileged-user-namespace restriction blocks WebKit's bubblewrap sandbox (`bwrap: setting up uid map: Permission denied`). The launcher now preflights this before WebKit crashes and prints the fix — a rendered AppArmor profile granting `userns` to this app's interpreter alone, kept narrow by `make install` giving the venv a private interpreter copy. `OBSIDIAN_READER_SKIP_SANDBOX_CHECK=1` bypasses the check.
- The sandbox stays on: WebKitGTK 2.52 ignores the old sandbox-disable variables, so the profile is the supported path, and it is the same mechanism Ubuntu ships for browsers.

## 0.2.0 — 2026-09-01

- Reading (zen) mode: `F11` hides the sidebar, header, and window chrome, leaving only the note; `Esc` or `F11` leaves, restoring the sidebar to how it was.
- PDF export: `Ctrl+Shift+E` (or the menu) prints the current rendered note to a user-chosen file through WebKit's print pipeline. A target inside the vault is refused — the zero-write promise covers exports too.
- The GUI smoke run now proves both on a live display, including the `%PDF` magic bytes of an actual export, and runs against isolated application state so a restored session cannot race it.

## 0.1.0 — 2026-09-01

First release. A read-only GTK4/libadwaita reader for Obsidian vaults.

- Opens a folder as a vault or a single note, in place, from the CLI, the file dialogs, drag-and-drop, or a recent-vaults list; a second launch hands its path to the running instance.
- Renders CommonMark and GFM plus the Obsidian layer: wikilinks with aliases, heading and block links, note/section/block embeds with cycle detection and a depth limit, callouts (foldable and nested), highlights, hidden comments (`%%` and HTML), inline tags, extended task states, footnotes (inline included), frontmatter as a collapsible Properties panel, image sizing syntax, and syntax-highlighted code.
- Resolves links path-first then by filename; ambiguous names open a chooser, never an arbitrary note; missing links are visibly marked.
- Vault-wide filename and full-text search with snippets, in-note find, back/forward history, outline navigation, light/dark/system appearance, zoom, session restore, and a read-only indicator.
- Security: JavaScript disabled in the rendering surface (the app refuses to start if it cannot be), raw note HTML escaped, generated HTML passed through an allowlist sanitizer, assets served only through a vault-contained URI scheme, remote resources blocked, `http`/`https` links handed to the system browser, every other scheme refused. Dataview/Templater/mermaid blocks render as labeled inert source.
- Resource bounds proven against real attack payloads: YAML aliases in frontmatter are refused (a 352-byte alias bomb froze property rendering before the fix), and a per-page embed budget caps multiplicative embed fan-out (six small notes rendered a 23 MB page in 29 s before the fix; 0.2 s after).
- Zero-write guarantee covered by a test that hashes a vault before and after a full index-and-render pass; the full suite is 77 tests plus a scripted GUI smoke run. CI (ruff, pytest on 3.12/3.13, semgrep) and `SECURITY.md` ship with the repo.
