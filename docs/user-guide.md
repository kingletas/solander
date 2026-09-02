# User guide

Everything the reader does, and the exact boundaries of what it will not. Installation and first launch are in [getting started](getting-started.md). This guide is also available inside the app — press `F1`, or find it in the menu.

The three promises frame every feature below: the vault is **never written**, note content is **never executed**, and the network is **never touched**.

## The window

A full-height rail on the left — a deep sepia surface against the reading canvas, crowned with the vault's name — resizable by its divider, with six pages switched by the icons under the name:

| Page | What it holds |
|---|---|
| **Files** | A collapsible Pinned & recent section (Note menu → Pin/Unpin Note), then the folder tree under its own label. Single click opens a note or expands a folder; middle-click or `Ctrl+click` opens a note in a new tab; right-click a folder hides it. |
| **Search** | Quick-open and full-text search (below). |
| **Links** | For the current note: every note that links to it, each with the line of context around the mention, then its outgoing links with missing and ambiguous targets named. |
| **Tags** | Every tag in the vault — inline and frontmatter — with counts and a filter box. Activating a tag runs a `tag:` search. |
| **Bookmarks** | The vault's own `.obsidian/bookmarks.json`, read-only, groups flattened. |
| **Graph** | The current note's neighborhood: bidirectional links in accent color, backlinks solid, outgoing dimmed. Click a node to open it. |

Every panel has a visible switch: the sidebar toggles from the button at the far left of the header (or `F9`), and the **outline panel** — the current note's headings, docked on the right with its own close button — from the list button on the right (or `F8`). Both toggles remember their state. The header also carries back/forward (WebKit's real history), search, and a quiet lock icon: click it for the read-only reason (the app cannot write by design, not by permission) and the next action — view raw source, open the note in your default editor, or reveal it in Files.

## Opening things

- `obsidian-reader ~/vault` opens a folder; `obsidian-reader note.md` opens a single file via its parent folder; bare `obsidian-reader` restores the last session (toggleable in the menu).
- A second launch hands its path to the running instance rather than racing it.
- Drag a folder or file onto the window; recent vaults live under the folder button.

## Navigation

- **Wikilinks** resolve the way Obsidian resolves them: exact relative path, then vault-root path, then filename match. An ambiguous name opens a chooser rather than guessing; a missing target renders as a labeled dead link.
- **Hover previews**: rest the pointer on a wikilink for a moment and a popover shows the opening of the target, rendered through the same pipeline. The popover takes no input — clicks always land on the page.
- **Tabs**: `Ctrl+T` new, `Ctrl+W` close (the last tab shows the welcome page instead of closing the window). Middle-click or `Ctrl+click` on tree notes and in-page wikilinks opens tabs; each tab keeps its own history and outline; open tabs restore with the session.
- **Outline**: the panel on the right (`F8`) jumps to any heading of the current note.

## Search

Two searches share the Search page:

- **As you type — fuzzy quick-open** over filenames (`Ctrl+P`). Subsequences match, word starts and filename hits rank higher, and an empty query lists your twenty most recent notes.
- **On Enter — full-text search** (`Ctrl+Shift+F`), ranked by relevance with prefix matching (`ship` finds "Ships"). Opening a result highlights its matches in the note.

Three operators narrow full-text queries, combinable with plain words:

| Operator | Meaning |
|---|---|
| `path:journal` | The note's path contains the term |
| `file:meeting` | The filename contains the term |
| `tag:project` | The note carries the tag — nested children match, so `tag:project` finds `project/alpha` |

## The note page

Every note opens with its context before its content:

- **Breadcrumb** — the note's folder path above the title; clicking an ancestor reveals that folder in the file tree.
- **Inline title** — the filename as a large serif title. When the note opens with an identical `#` heading, the body's copy yields, so the title appears exactly once.
- **Metadata line** — updated date, word count, an approximate read time on longer notes, and the note's frontmatter tags as clickable chips (a chip runs a `tag:` search).
- **Linked mentions** — notes that link to the current one are listed after the content, collapsed, each with the line of context around the mention. The Links panel carries the full list either way.

**Every one of these is a choice, not a fixture.** View → Note Context toggles Title & Breadcrumb, the Metadata Line, and Linked Mentions individually — persisted across sessions, applied to every open tab at once. The note's headings live in the outline panel (`F8`), which is a real panel with a real close button, not something printed into the page.

## What renders

CommonMark and GFM (tables, task lists, strikethrough, autolinks), plus the Obsidian layer: wikilinks with aliases and heading/block links, embeds with cycle detection, callouts (foldable and nested), highlights, hidden `%%` and HTML comments, inline tags, extended task states, footnotes, image sizing, frontmatter as a collapsible Properties panel, syntax-highlighted code, and TeX math (`$...$`, `$$...$$`) as native MathML. Beyond markdown:

- **Canvas** (`.canvas`) files open as static positioned pages — cards, groups, colors, labeled arrows — with file cards linked to their notes.
- **Kanban** board notes render as boards: headings become columns, task items become cards (their wikilinks work), done cards dim, and everything after `***` is the archive lane.
- **Excalidraw** notes render as static SVG at their drawn positions, including the compressed format.
- **Bases** (`.base`) files render their table views — filters, column order, sort, display names. Plugin view types (TaskNotes and similar) are named as not rendered rather than imitated.
- **Mermaid diagrams** render as static SVG, drawn by a pure-Python layout engine — flowcharts (shapes, edge labels, subgraphs, `style`/`classDef` stroke styling), sequence diagrams, and pies, which is ~98% of a real vault's blocks. Other diagram kinds (gantt, state, timeline…) show as labeled source naming the kind. Mermaid's own JavaScript renderer is never involved.

### Dataview

DQL queries evaluate in pure Python against the live index — results update as the vault changes:

- `TABLE` (with `WITHOUT ID` and `AS` aliases), `LIST`, and `TASK` heads.
- `FROM` folder (`"01 Journal"`), tag (`#project`), or `[[]]` (notes linking here), combined with `and`/`or` and negation.
- `WHERE`, `SORT`, `GROUP BY`, `FLATTEN`, `LIMIT`, applied in the order written and repeatable.
- `this.` for the query's own note, bracket access for spaced field names, lambdas in `filter`/`map`, date and duration arithmetic, and the common function library (`choice`, `default`, `dateformat`, `dur`, `contains`, `length`, `sum`, `round`, and friends).
- Inline expression spans evaluate in place.

Anything outside that surface renders as the original source with a label saying exactly why — never a partial result. `dataviewjs` is never executed; it renders as labeled source, by design.

## Reading a book

Right-click a folder of chapters — a manuscript's `Chapters/`, say — and choose **Read as Book**. The reader becomes a lectern: reading mode opens on your last-read chapter, each page is the chapter alone (title, prose, and the way onward — no vault machinery), and turning a chapter slides the old page away like a leaf.

- **Real pages, no scrolling.** Each chapter is laid out into screen-sized pages by WebKit's own print pipeline — exact line breaks, nothing to scroll. `N`/`P`, the arrow keys, Space, and PageUp/Down turn pages; clicking the right side of the page turns forward, the left third turns back. The last page turns into the next chapter, and turning back past a first page lands on the previous chapter's last. A quiet line at the page's foot keeps your place: *chapter 4 of 37 · page 3 of 12*. (Without the Poppler bindings, book mode falls back to chapter-at-a-time with vertical reading.)
- **The book's own dress**: chapters carrying `cssclasses` take their vault snippet's design — including its `@font-face` fonts, which load from the vault's own `.obsidian/fonts` and nowhere else — and the desk behind the page is tinted from the book's declared paper color. Books without a stylesheet get a built-in book treatment: justified serif, a drop cap, centered chapter titles.
- **Progress is remembered** per book, in the reader's config. `Esc` closes the book and the vault comes back.

## Hidden folders

Right-click a folder in the tree to hide it from the tree, quick-open, and search results. The toast offers Unhide; View → Unhide All Folders clears the reader's list for this vault. Two boundaries:

- Obsidian's own excluded-files setting (`userIgnoreFilters` in `.obsidian/app.json`) is honored read-only on top and is not affected by Unhide All.
- The Links, Tags, Graph panes and Dataview results stay complete: they answer explicit questions, and a query that silently omits rows would be lying.

The hidden list is stored in the reader's config, never in the vault.

## Mind map

`Ctrl+M` (or Note menu → View as Mind Map) lays the current note's headings and nested bullets out as a tree — colors by depth, heading nodes linking to their place in the note. `Ctrl+M` again, the link at the top of the map, or Back returns to the markdown.

## Reading comfort

- **Reading mode**: `F11` removes every piece of chrome; `Esc` or `F11` restores.
- **Typography** (menu): font (the default is a book serif; sans and mono are one click away), line width (narrow to full), line spacing (compact to relaxed) — persisted, applied everywhere.
- **Appearance** (menu): the **theme** first, then the **mode**. **Atelier** is the default — a parchment manuscript by day, a candlelit nocturne by night — and takes follow system, light, or dark. **Blood Record** is a dark archive: charcoal and bone, oxidized copper for what is important, dried blood for the structure, and one hot red kept for what actually matters — a critical callout, a broken link, the document under your hand. It has no light mode, so choosing it greys the mode choice out rather than ignoring it; the mode you had comes back with Atelier. Both are remembered. **Zoom**: `Ctrl` `+`/`-`/`0`.
- **Vault CSS snippets**: the snippets your vault enables apply, reduced by a strict sanitizer (anything network-reaching or escaped is dropped). Pages carry the `markdown-preview-view` class and the note's `cssclasses`, so class-scoped snippets match. Toggle under View.

## Exports and PDFs

- **Export as PDF** (`Ctrl+Shift+E`) prints the current rendered note through a print stylesheet: wide code and tables wrap instead of clipping, boxes are kept whole across page breaks, headings stay with their content, and the palette prints light. A target inside the vault is refused — the zero-write promise covers exports.
- **Viewing PDFs**: with `gir1.2-poppler-0.18` installed, clicking a PDF opens an in-app viewer (fit-to-width, zoom, Open Externally, `Esc` closes). Without it, PDFs open in your system viewer.
- **Raw source** (`Ctrl+U`) shows any note's markdown verbatim; Copy Markdown Source / Copy Vault Path / Copy as Wikilink live in the menu.

## The live index

The vault is watched while open: creations, edits, deletions, and renames re-index in the background after a two-second quiet period, refreshing the tree, search, link panels, and any visible Dataview results. The index persists per vault under `~/.cache/obsidian-reader/` — cold builds are tens of seconds on a very large vault, warm launches about a second. The cache is derived data: corruption rebuilds it silently, and Clear Index Cache in the menu does so on demand. Expect it to cost disk roughly proportional to the vault's text.

## Keyboard shortcuts

| Keys | Action |
|---|---|
| `Ctrl+P` | Quick open |
| `Ctrl+Shift+F` | Search the vault |
| `Ctrl+F` | Find within the note |
| `Ctrl+O` / `Ctrl+Shift+O` | Open file / vault folder |
| `Alt+Left` / `Alt+Right` | Back / forward |
| `Ctrl+T` / `Ctrl+W` | New tab / close tab |
| Middle-click or `Ctrl+click` | Open note or link in a new tab |
| `Ctrl+M` | Toggle the mind map |
| `F11` / `Esc` | Reading mode in / out |
| `N` / `P`, arrows, Space | Turn the page (book mode) |
| `F8` | Toggle the outline panel |
| `F9` | Toggle the sidebar |
| `Ctrl+R` | Reload |
| `Ctrl+U` | Raw source view |
| `Ctrl+Shift+E` | Export as PDF |
| `Ctrl` `+` / `-` / `0` | Zoom in / out / reset |
| `Ctrl+?` | Shortcut list |

## Configuration reference

State lives outside every vault: `~/.config/obsidian-reader/` (session, preferences, hidden folders) and `~/.cache/obsidian-reader/` (the per-vault index). The resource bounds are environment-overridable — the defaults are generous, and each exists so hostile input cannot grow without limit:

| Variable | Bounds |
|---|---|
| `READER_MAX_NOTE_BYTES` | Largest note opened as text (10 MB) |
| `READER_MAX_FRONTMATTER_BYTES` | Largest YAML block parsed (128 KB) |
| `READER_MAX_EMBED_DEPTH` / `READER_MAX_EMBEDS_PER_PAGE` | Embed nesting (5) and count per page (200) |
| `READER_PREVIEW_MAX_CHARS` | Hover preview slice (2,500) |
| `READER_MAX_MATH_CHARS` | Longest TeX converted (5,000) |
| `READER_MAX_LINKS_PER_NOTE` / `READER_MAX_MENTIONS_PER_TARGET` / `READER_MAX_TASKS_PER_NOTE` | Graph bounds (2,000 / 1,000 / 2,000) |
| `READER_MAX_BOOKMARKS` / `READER_MAX_BOOKMARK_BYTES` | Bookmarks file bounds (500 / 1 MB) |
| `READER_MAX_CANVAS_NODES` / `READER_MAX_CANVAS_BYTES` | Canvas bounds (1,000 / 5 MB) |
| `READER_MAX_DRAWING_ELEMENTS` / `READER_MAX_DRAWING_BYTES` | Excalidraw bounds (3,000 / 10 MB) |
| `READER_MAX_MINDMAP_NODES` | Mind-map nodes (500) |
| `READER_MAX_DIAGRAM_NODES` | Mermaid flowchart nodes (400) |
| `READER_MAX_SNIPPET_BYTES` / `READER_MAX_BASE_BYTES` | CSS snippets total (256 KB) and base file size (1 MB) |
| `OBSIDIAN_READER_SKIP_SANDBOX_CHECK` | Skips the launch preflight (for environments that confine WebKit themselves) |

## Troubleshooting

- **A setup window appears instead of the reader, or a terminal launch prints an AppArmor profile** — the one-time sandbox step; see [getting started](getting-started.md#3-first-launch--the-one-time-sandbox-step). If the profile is installed but the app still refuses, it was started around its launcher: a `#!` shebang launch bypasses AppArmor's attachment. Start it from the applications grid or via `obsidian-reader`.
- **Dataview blocks say "the index is still building"** — the first index of a large vault is running; they render on their own when it finishes.
- **A Dataview block shows its source with a reason** — that query uses syntax outside the supported surface; the label says which part.
- **A mermaid block shows its source with a reason** — the diagram kind is outside the supported three (flowchart, sequence, pie), or a line could not be read; the label says which.
- **A CSS snippet has no visible effect** — snippets written against Obsidian's own interface (sidebars, tabs, editor) target elements that do not exist here; note-content snippets (callouts, checkboxes, `cssclasses`-scoped styling) are the ones that carry over. Declarations using `url()` are removed by the sanitizer regardless.
- **Search misses a brand-new note** — wait a moment; the debounce is two seconds plus the re-index. `Ctrl+R` forces it.
- **The index seems wrong** — Clear Index Cache in the menu rebuilds from scratch.
