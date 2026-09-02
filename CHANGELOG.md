# Changelog

## 1.2.0 — 2026-09-01

The GUI-first release: nothing about installing or using the reader requires a terminal beyond one paste.

- **The one-time sandbox step is now a window.** Launched from the applications grid on a stock Ubuntu, the reader used to die silently to stderr; it now opens a plain-GTK setup window (no WebKit needed — that is the part that cannot start) explaining the situation, offering a single copy-paste command, and relaunching the reader itself when "check again" finds the profile installed. The terminal flow still works headless, unchanged.
- **The documentation lives inside the app.** `F1` opens the user guide, the menu carries Getting Started beside it, and the welcome page links both — rendered through the reader's own pipeline, so a fresh install can read its manual before opening any vault. The docs ship with the package.
- The README and getting-started guide now lead with the desktop flow — app grid, welcome page, Open With from the file manager — with the CLI as the alternative. (Markdown files and folders were already registered for Open With; that part just needed saying.)

## 1.1.1 — 2026-09-01

- **The mind map now has an obvious way back.** The map page carries a "Back to <note>" link, `Ctrl+M` toggles — note to map, map back to note — and the map keeps counting as its note, so the window title, tree selection, and the toggle itself all keep working while it is shown. (Back always worked; nothing said so.)

## 1.1.0 — 2026-09-01

- **Folders can be hidden.** Right-click a folder in the tree to hide it — it leaves the tree, quick-open, and search results (link panels, graph, and Dataview stay complete, since those answer explicit questions). The toast offers Unhide, and View → Unhide All Folders clears the reader's list. Obsidian's own excluded-files setting (`userIgnoreFilters` in `.obsidian/app.json`) is honored read-only on top, and stays in force when the reader's list is cleared. The reader's list lives in its own config, never in the vault.
- **Any note can be viewed as a mind map** (`Ctrl+M`, or Note menu → View as Mind Map): headings and nested bullets become a right-growing tree of rounded nodes with per-depth colors, heading nodes link to their place in the note, and Back returns to the rendered page. Static SVG, no JavaScript, labels cleaned of markup and escaped.

## 1.0.0 — 2026-09-01

The completion release: the reader now renders every content type the vault it was built against actually contains.

- **Kanban boards render as boards.** A note with `kanban-plugin` frontmatter shows its `##` headings as columns and its task items as cards — wikilinks inside cards resolve, done cards dim, the `***` archive becomes its own lane, and boards scroll horizontally (and wrap in print). Verified against 125 real boards holding 6,545 cards.
- **Excalidraw drawings render as static SVG** — rectangles, ellipses, diamonds, arrows, lines, freehand strokes, and text, at their drawn positions and rotations. The LZ-String compression Excalidraw uses is decoded by a pure-Python port (decode-only); the JSON is treated as hostile input like canvas.
- **Vault CSS snippets apply.** The snippets `.obsidian/appearance.json` enables load through a strict allowlist sanitizer — plain rules and @media blocks survive; any declaration that could touch the network or smuggle an escape (`url()`, `@import`, `expression()`, a backslash) is dropped whole. Pages carry Obsidian's `markdown-preview-view` class and the note's own `cssclasses`, so class-scoped snippets match. A View-menu toggle turns them off.
- Accessibility: the local-graph pane carries an accessible label; tree rows already announce their note names.
- The Flatpak manifest's dependency list is current. Building it still needs `flatpak-builder`, which is not installed here — the build remains unverified and says so.

## 0.9.0 — 2026-09-01

Dataview, in pure Python — no JavaScript, same as everything else.

- **DQL queries evaluate.** `TABLE` (with `WITHOUT ID` and aliases), `LIST`, and `TASK` blocks run against the live index: `FROM` folder/tag/`[[]]` sources with `and`/`or`/negation, chained `WHERE`/`SORT`/`GROUP BY`/`FLATTEN`/`LIMIT` in written order, `this.` context, bracket access for spaced field names, lambdas in `filter`/`map`, date and duration arithmetic, and a 30-function standard library (`choice`, `default`, `dateformat` with Luxon tokens, `dur`, `contains`, `length`, and friends). Results are live: the vault monitor already re-renders what changes.
- **Inline expressions evaluate** — the `= this.field` spans templates lean on render their values in place.
- **`.base` files render**: table views with filters (`and`/`or`/`not` over the Bases expression dialect — `file.hasTag`, `file.inFolder`, `file.hasProperty`, comparisons, `today()` date math), column order, sort, and displayName mapping. Plugin view types (TaskNotes and similar) are named as not rendered, never faked.
- **Anything outside the surface degrades honestly**: the block renders as labeled source with the parser's reason, and `dataviewjs` stays inert by design.
- **Acceptance against a real 10,700-note vault**: 481 of 486 Dataview blocks evaluate (99% — the five failures are deliberately broken examples inside an archived chat export) at 58 ms average, 1,203 of 1,206 inline expressions, and all six `.base` files row-for-row correct against grep ground truth.
- Fixed en route, and it matters beyond Dataview: PyYAML reads YAML 1.1, where a bare `Yes` is a boolean — Obsidian keeps it a string, so `Outage: Yes` never matched `== "Yes"`. The frontmatter loader now resolves only `true`/`false` as booleans, matching Obsidian.
- The index schema bumped (cached scans now carry frontmatter and tasks), so the first launch after upgrading rebuilds the cache — cold ~21 s on a 10,700-note vault, warm ~2 s after.

## 0.8.1 — 2026-09-01

- **Fixed PDF export splitting and clipping content.** The stylesheet had no print rules, so paper got the screen layout: code and tables kept their scroll containers (which clip on paper — long lines simply vanished off the right edge), and boxes could be sliced across page boundaries. A print stylesheet now makes wide code and tables wrap instead of clip, keeps code blocks, callouts, tables rows, images, math, and the properties panel whole across page breaks, keeps headings attached to what follows them, repeats table headers on each page, forces the light palette (backgrounds are not printed, so a dark-theme export was pale-gray text on white paper), hides media players, and prints only the open state of foldable sections.
- The GUI smoke now proves export quality in both directions, not just that a PDF exists: the tail of an overflowing code line must survive into the extracted text, the ink of a known word must be dark even when exporting from the dark theme, and an eight-block document must reach page two with no block straddling a page boundary — each check shown to fail against the unfixed stylesheet.

## 0.8.0 — 2026-09-01

- **Embedded PDF preview.** Opening a PDF from the file tree (or a PDF embed's link) now shows it in an in-app viewer: pages rendered on demand through the system's own Poppler library, fit-to-width with zoom, an Open Externally escape hatch, and a page cap plus a small surface cache bounding memory. Requires the optional `gir1.2-poppler-0.18` package; without it, PDFs open externally exactly as before — the viewer is never half-present.

## 0.7.0 — 2026-09-01

The fidelity layer: more of what a vault actually contains renders as itself.

- **Math.** `$...$` and `$$...$$` TeX renders as native MathML (via latex2mathml — pure Python, no JavaScript), with block math centered and inline math in the text flow. Currency stays prose: an opener must touch its content and a closer may not be followed by a digit, so "$5 and $10" never becomes a formula. TeX the converter refuses — or anything over the size bound — falls back to the labeled source.
- **Canvas files render.** A `.canvas` opens in the reading pane as a static page: text cards, file cards (linked to their notes), groups, colors, and SVG arrows with labels, laid out at the canvas's own coordinates. Verified against all 26 canvases in a 10,000-note vault. The JSON is treated as hostile: coordinates are numerically coerced per node, colors pass a palette-or-hex check, every string is escaped, and node/size bounds cap the work.
- **Typography controls.** Menu → Typography: font (theme default, serif, sans, mono), line width (narrow to full), and line spacing (compact to relaxed) — persisted, applied to every page including previews and canvases.
- Deferred, named: embedded PDF preview needs `gir1.2-poppler-0.18`, which is not installed here — code that cannot be run even once does not ship. External open remains. Heading folding stays out for a structural reason: without JavaScript, a `#anchor` cannot open the closed `<details>` it lands in, so folding would break outline navigation.

## 0.6.0 — 2026-09-01

The retrieval layer: finding a note now works the way the best launchers do.

- **Fuzzy quick-open.** The as-you-type filename search matches subsequences with scoring — word-boundary hits, consecutive runs, and filename matches rank higher — so `scnt` finds "Second Note" and `pmn` finds "Personal/Meeting Notes". An empty query shows your recent notes.
- **Recent notes** are remembered across sessions (the twenty most recently opened).
- **Search hits open highlighted**: activating a full-text result highlights every match of the leading term in the opened note and scrolls to the first one.
- **A local graph pane** — a sixth sidebar page drawing the current note and its neighbors natively (no JavaScript): bidirectional links in accent color, backlinks solid, outgoing dimmed. Click a node to open it. Capped at thirty neighbors so hub notes stay legible.
- **Fixed a crash that could kill the app at any moment after 0.5**: Python's garbage collector can run on the index-sync thread, and cyclic garbage there can hold GTK and WebKit objects (a closed tab's web view) whose finalizers abort off the main thread — silently, with no message. Automatic collection is now off and the main loop collects on a timer, so GObjects are only ever finalized where they were born. Found because the GUI smoke started dying with exit 134 *after* printing an all-green PASS.

## 0.5.0 — 2026-09-01

The live layer: the reader now tracks the vault while it is open, and remembers it between launches.

- **A persistent index** in `~/.cache/obsidian-reader/`, one SQLite file per vault: note scans plus an FTS5 full-text index. A launch reads only what changed since last time — on a 10,600-note vault, a warm start indexes in ~1.2 s instead of ~8.5 s, and the first-ever build is ~9 s. The cache is derived data: corruption or a schema change wipes and rebuilds it silently, and "Clear Index Cache" in the menu does the same on demand. Expect it to cost disk roughly proportional to the vault's text (about half its size).
- **The vault is watched.** Every non-hidden directory carries a file monitor; changes are debounced for two seconds, then a background sync re-reads only the changed notes, re-resolves every link, and refreshes the tree, panels, and search — so a note written by another app (or synced in from another device) is searchable and backlinked without touching Reload. A rename or deletion re-resolves links vault-wide, so a link that was "missing" resolves the moment its target appears.
- **Full-text search is now ranked** by FTS5's BM25 relevance instead of index order, with token-prefix matching (`ship` finds "Ships") and match snippets from the index itself. Queries run in ~65 ms against 10,600 notes. Query text is quoted into plain prefix terms, so FTS query syntax can never be injected.
- The `path:`, `file:`, and `tag:` operators, the graph, and every panel work exactly as before — the graph now assembles from cached scans in about a second.
- Fixed en route: the first cold build took 131 s because deleting an FTS row by its unindexed `rel` column is a full-table scan — O(n²) across a build. Deletion now goes through a stored rowid; 131 s → 8.8 s.

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
