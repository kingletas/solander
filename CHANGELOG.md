# Changelog

## 2.2.3 — 2026-09-02

- **Frontmatter works in notes with Windows line endings.** A leading YAML block delimited with CRLF is now recognized like the same block with Unix line endings, so its title, tags, CSS classes and plugin metadata no longer appear as Markdown body text. Contributed by Mark Hodge.
- **Every continuous-integration action moved to its current major version**, each still pinned to a commit. The artifact actions are used only when publishing a release, so this is the first release to exercise them.

## 2.2.2 — 2026-09-02

Two defects found by installing the published package rather than trusting the build.

- **The Flatpak refused to start.** The check that decides whether WebKit's sandbox can run probes `bwrap --unshare-user`, and inside Flatpak that probe always fails — the process is already in Flatpak's own user namespace and nesting another is refused — **while WebKit's sandbox works perfectly, because Flatpak is the confinement**. So the one install route documented as needing no setup was the only one that would not open, and the AppArmor fix it printed could never have changed the result. The probe is skipped inside Flatpak, and two tests hold the line: one that it is skipped there, one that it still runs everywhere else.
- **The application reported the wrong version.** `__version__` in the package and `version` in `pyproject.toml` are two literals, and only the second is what the release job checks against the tag and the changelog — so 2.2.1 shipped announcing itself as 2.2.0. A test now asserts the two agree, and both workflows assert that the installed package prints the version they built.
- **CI now launches what it builds.** The Flatpak job checked `--version` and rendered a page in-process; neither goes through the startup path, which is why a Flatpak that could not start passed every gate. It now asserts the sandbox check answers correctly inside the bundle.


## 2.2.1 — 2026-09-02

A documentation and metadata pass after the first release.

- **The AppStream metainfo did not validate**, which matters because it is the file a software centre reads and Flathub refuses a submission whose metainfo fails. It had no homepage URL, used a deprecated developer tag, and carried **no screenshots, categories or keywords at all** — so the app would have appeared in GNOME Software as a name and a paragraph. It now carries the five project URLs, two screenshots, the categories and keywords the desktop entry already declared, and branding colours taken from the app's own icon.
- **Nothing validated either the desktop entry or the metainfo.** `make check` now runs both, and CI installs the validators so the check always runs there rather than degrading to a skip. That is how the metainfo came to be invalid without anyone knowing.
- **Getting started only knew how to build from source.** It walked a new reader through installing `uv`, cloning the repository and the one-time sandbox step — while a released Flatpak skips all of it. It now leads with the two packaged installs and marks the sandbox step as source-only.
- **The Flatpak instructions could not be followed.** The bundle is 3 MB and does not contain the GNOME 50 runtime it needs, so installing it requires a remote that provides the runtime. Neither document said so. Both now do, along with the note that a Flatpak install puts no `solander` on the `PATH`.
- **Every GitHub Action is pinned to a commit SHA** rather than a moving major tag, so a compromised or rewritten tag cannot change what runs in CI. A pinned SHA never moves, which is also the risk — a Dependabot configuration now opens a pull request when a pinned action releases a new version, so the pins do not quietly freeze this repository on the day they were written.
- **The documentation is checked the way the code is.** A new test resolves every relative link and heading anchor across the six documents, asserts that package filenames in the docs match the version in `pyproject.toml`, and asserts that the theme counts written in prose match the registry. It caught a link broken by renaming a heading in this same pass. The changelog is exempt from the last two: it records what was true at each release.


## 2.2.0 — 2026-09-02

Tagging a release now builds and publishes the packages.

- **Debian package.** `packaging/deb/build.sh` produces an `Architecture: all` deb — every dependency is pure Python — that vendors the app and its libraries into `/usr/lib/solander`, declares the GObject bindings as apt dependencies, and **ships the AppArmor profile**, parsed by the postinst. A deb user has no sandbox step at all.
- **Flatpak.** The manifest is real now rather than a starting point, and **built, bundled, installed and run before shipping**: the GNOME 50 runtime, every dependency pinned by sha256 because flatpak-builder builds with the network off, and no network permission granted at runtime. Three things were wrong on the way and each is worth knowing: the SDK has no `hatchling`, so `--no-build-isolation` could not build the app until the backend was pinned too; `pygments` existed in the SDK and was therefore **skipped**, which would have shipped a bundle missing it, so every dependency is now installed with `--ignore-installed`; and **GNOME 48 is end-of-life**, which for a WebKit application means an unpatched browser engine. `PyYAML` is the one dependency whose wheel is tied to the runtime's Python ABI, and the manifest says so. Inside Flatpak there is no AppArmor step either — the sandbox WebKit needs comes from Flatpak's own bubblewrap.
- **`Release` workflow.** Push a `v*` tag and it builds both, **installs each one and checks what it put on the system**, then publishes them on a GitHub Release whose body is that version's changelog section. It refuses to start when the tag, `pyproject.toml` and the changelog disagree.
- **CI builds the packages too**, so a tag is never the first time the packaging runs: the deb on every change, the flatpak on pushes to main. Both go further than building — each installs its package and **renders a page inside it**, because `--version` imports almost nothing and would have passed with a dependency missing.
- **The profile names the right thing for each install shape.** From source it names the private interpreter in the virtualenv; from a system package it names `/usr/bin/solander`, because naming `/usr/bin/python3` would grant user namespaces to every Python process on the machine. That is the shape Ubuntu's own profiles for packaged Python applications use.
- `make deb`, `make flatpak` and `make notes VERSION=x.y.z` run the same scripts CI runs.
- **The unit suite no longer needs GTK to run, and a test now says so.** One test reached into the window layer for a function that only builds a string; it passed on any machine with the GObject bindings installed and failed on a clean one, which is what CI is. The string-builder moved beside the profile it wraps, and two checks hold the line: the core and the CLI are imported in a fresh interpreter with `gi` blocked, and no unit test may import `solander.gui`. Both were proven against a deliberate breach.
- **The packaging scripts were untracked when first written**, for the third time from the same cause: this machine's global `core.excludesFile` refuses `*.sh`, and the negation added when the installer hit it was scoped to `scripts/` alone. The release workflow would have failed on a file that had never been pushed. The negation now covers the whole repository, and every shell script in the tree is confirmed tracked.

## 2.1.1 — 2026-09-02

Documentation pass before the first public push.

- **The name is explained**, in the README and in the About dialog: a solander is the clamshell box an archive keeps its documents in — open it to look at something, close it, and nothing has changed.
- **Screenshots**, of both the default theme and the Archive family.
- **CONTRIBUTING.md**: the three promises a change is measured against, how the virtualenv has to be built for the GI bindings to be visible, what the smoke run covers, and where code belongs.
- The About dialog links the project and its issue tracker.
- Fixed the rename's one grammar slip — *"puts an `solander` launcher"* — in the README and getting started.

## 2.1.0 — 2026-09-02

Two flags for the sandbox, the same two in every app here.

- **`--sandbox`** prints the AppArmor profile this installation needs and nothing else, so it pipes: `solander --sandbox | sudo tee /etc/apparmor.d/solander`. It replaces the documented recipe of `sed`-ing the profile out of the app's own stderr, which only worked while the app happened to be failing.
- **`--sandbox-status`** reports the profile, the interpreter, the AppArmor label and whether bubblewrap can actually unshare — and names the two failures that look identical from the outside: a profile naming a **shared interpreter** (which would grant user namespaces to every process using it), and a profile that is installed but **did not attach** to this process. Exits non-zero while anything is wrong.

## 2.0.3 — 2026-09-02

- **The mark fills its cell.** Enlarging the standalone silhouette was not enough: a plate on a plinth simply carries less ink than the near-full-bleed shapes it sits beside, so it kept reading as half-size in a dock. The sigil now sits on its own tile — **88% coverage against a neighbour's 82%** — with the record, the cut, the seal and the ledge inside it. The identity is unchanged, and it still re-tints per theme. Compared against a square and a round neighbour at 96, 64, 48, 32 and 24px, in five themes, and in silhouette.

## 2.0.2 — 2026-09-02

- **The mark fills its canvas.** The sigil covered 38% of the 128px square, so beside near-full-bleed neighbours it read as half-size in a dock. The geometry is unchanged in kind — plate, cut, seal, plinth — and now covers about 75%: a wider plate, a full-width plinth, and a larger seal. Checked against a square and a round neighbour at 64, 48, 40, 32 and 24px.

## 2.0.1 — 2026-09-02

The window had never carried its own icon, and the rename made it visible.

- **The process now identifies itself as the app id.** Wayland takes a toplevel's app id from the program name, and the desktop matches a window to its `.desktop` file — and therefore to its icon — by exactly that. Launched as `python -m solander.cli`, the program name was `cli.py`, which matches nothing, so the window and its dock entry drew a placeholder. `GLib.set_prgname(APP_ID)` fixes it, and a smoke check asserts it. **This was true under the old name too; the rename only made it noticeable.**
- **The installer refreshes the icon theme cache.** A stale `icon-theme.cache` takes precedence over the directory it sits in, so an icon installed after the cache was written is invisible — which is exactly what happened: the cache still listed `com.kingletas.ObsidianReader` and did not list `com.kingletas.Solander`. `install.sh` and `uninstall.sh` now rebuild the cache, or delete it when the theme has no index file.
- A unit test asserts the desktop entry, the metainfo and the icon filename all agree with `APP_ID`, so a future rename cannot half-land.

## 2.0.0 — 2026-09-02

**Obsidian Reader is now Solander.**

A solander is the clamshell box an archive keeps its documents in — which is the job: present the record, and leave it exactly as it was found. The old name described the first version of the app and had stopped describing this one, and it borrowed a trademark it has no claim to. Obsidian compatibility is unchanged and total; it is now a property rather than the product's name.

- **New identity**: the app is `Solander`, the command is `solander`, the app id is `com.kingletas.Solander`, and the Python package is `solander`. The desktop entry keeps `GenericName=Markdown Reader` and `Keywords=…obsidian…`, so searching your applications for "obsidian" or "reader" still finds it.
- **Your state comes with you.** The first launch adopts `~/.config/obsidian-reader` and `~/.cache/obsidian-reader` under the new names — recent vaults, theme, pinned notes, book progress and every vault's index — so the rename is not a reset. Adoption only happens when the new directory does not exist yet, so it can never overwrite live state.
- **Environment overrides renamed** to match: `SOLANDER_HOME`, `SOLANDER_SKIP_SANDBOX_CHECK`, `SOLANDER_FORCE_SETUP`. The `READER_MAX_*` bounds keep their names.
- **The AppArmor profile is now `/etc/apparmor.d/solander`.** It names the interpreter by path, so moving the checkout requires reinstalling it — `solander` prints the profile rendered for your installation, and the old `/etc/apparmor.d/obsidian-reader` can be deleted.
- Nothing about the reading surface changed: same fourteen themes, same mark, same renderers.

**Two defects in the install path, found while moving the checkout:**

- **`scripts/install.sh` and `scripts/uninstall.sh` were never in the repository.** `~/.gitignore` is `core.excludesFile` for every repo on this machine and it excludes `*.sh`, so git had silently refused both files since the first commit — a clone had no installer, and `make install` would have failed on a `No such file or directory` for a file the README tells you to run. A repo-local `!scripts/*.sh` negation overrides it, and both are committed now.
- **`make install` built a virtualenv the app could not start from.** Where no `.venv` existed yet, `uv sync` created one on uv's own interpreter, without system site packages — so `import gi` failed and the GTK bindings were invisible. It now creates the venv against the system Python the way `make sync` does, and **refuses to report success if the venv cannot import `gi`**, naming the apt packages to install.

## 1.14.0 — 2026-09-02

Blood Record became a family of thirteen.

- **The Archive family.** *Blood Record*, *Ember Archive*, *Blackout*, *Corrosion*, *Bruise*, *Drowned*, *Sepulcher*, *Cold Iron*, *Hazard*, *Velvet Knife*, *Ash*, *Null* and *Black Blood* — thirteen dark themes sharing one design language and one stylesheet. Appearance → Theme, now grouped by family.
- **A theme is a palette.** Sixteen colours in `core/palettes.py` and no rules: the page tokens, the whole GTK chrome and the syntax palette are all generated from them. Adding the fourteenth is one entry.
- **Semantics hold across the family**: danger, warning, verified and information mean the same thing in every theme, and a broken link takes the theme's danger colour rather than its accent.
- **Every colour that carries words is measured.** A solver lifts any text colour that misses WCAG AA on the ground it sits on, and the suite asserts it for all thirteen themes — body text, muted text, links, code, callout titles and the rail's labels — against the page, the panels, and the code ground. **This caught three failures in Blood Record as shipped**: its link (4.44), its hot red as a broken-link marker (3.88) and its rail labels (2.48). Its surfaces and accent are unchanged; only the colours carrying text moved.
- Atelier is untouched.

## 1.13.0 — 2026-09-02

The app mark is a sealed record now, not a book with a padlock.

- **One sigil, two identities.** A bound archival plate standing on a plinth, with a diamond **cut through the plate** and a seal set into the cut. The geometry is identical in both themes; only three fills change — lapis board and gold seal in Atelier, dried blood and arterial red in Blood Record — and the welcome page re-tints them in CSS, so the mark follows the theme without a second file.
- **Built to survive 16px**: no gradients, filters, masks, rasters, text or external references; three paths, integer coordinates, the seal cut with `fill-rule="evenodd"` rather than a mask. Checked at 128, 64, 48, 32, 24 and 16, in silhouette, and reversed.
- The padlock, the ruled text lines and the gradients are gone — they made it a generic document app with security software bolted on.

## 1.12.0 — 2026-09-02

A second theme, and a place for the next one.

- **Blood Record.** A dark archive rather than a notebook: charcoal and bone, oxidized copper for what is important, dried blood for the structure, and one hot red held back for what actually matters — a critical callout, a link that resolves to nothing, the document currently under your hand. It dresses the whole application, rail and menus included, and brings its own syntax palette. Appearance → Theme.
- **The original theme is untouched.** Atelier keeps its parchment, its gold and its lapis links, byte for byte; the new theme is layered over the dark palette rather than replacing anything.
- **A theme is a palette now, not a rewrite.** Page tokens, chrome colors and syntax colors live in one registry, and the chrome structure names those colors instead of hardcoding them — so a further theme is a palette and nothing else. The sidebar's CSS class stopped being named after one theme.
- **A dark-only theme greys out the light/dark choice** rather than accepting it and ignoring it; the mode you had comes back when you return to Atelier.
- Print is untouched: the theme is screen-only, so PDF export still renders on white through the same print stylesheet.

## 1.11.1 — 2026-09-02

- **The place indicator can no longer overlap the page.** It sits in its own strip below the page instead of floating over the last line.
- **Pages keep a book's measure.** The printed page is capped at a focused width (~880px) regardless of screen size, centered on the desk — on a large monitor the book is a book, not a wall.
- **The desk is opaque.** The paged view paints the desk color behind the page, so nothing shows through around it, and showing pages re-asserts reading mode.

## 1.11.0 — 2026-09-02

Book mode turns pages now, not chapters.

- **Real pagination, no scrolling.** Opening a book prints each chapter through WebKit's own print pipeline at exactly the reading area's size — true page breaks with line integrity, no JavaScript anywhere — and Poppler draws the pages one at a time. `N`/`P`, arrows, Space and PageUp/Down turn pages with the slide animation; clicking the right side of a page turns forward, the left third back.
- **Chapters roll over at their covers.** The last page turns into the next chapter; turning back past a first page lands on the previous chapter's *last* page. A quiet indicator at the page's foot reads *chapter 4 of 37 · page 3 of 12*.
- Book pages print their own colors: the chapter's stylesheet background (a manuscript's parchment included) survives into the printed page via print-color-adjust, and the book-nav footer stays out of print — navigation is keys and clicks.
- Printed chapters are cached for the session, so returning to a chapter is instant; without Poppler, book mode falls back to 1.10.0's chapter-at-a-time behavior.

## 1.10.0 — 2026-09-02

Book mode: the reader as a lectern for the manuscripts themselves.

- **Read as Book** (right-click a folder of chapters): reading mode opens on your last-read chapter, every page is the chapter alone — title, prose, and the way onward — and each chapter ends with its neighbors by name plus your place in the book. `N`/`P` turn chapters; progress is remembered per book; `Esc` closes the book.
- **Pages turn like pages.** Changing chapters slides the old page away over the incoming one — a GTK-side animation on a snapshot of the outgoing page, so the no-JavaScript rule is untouched.
- **The book wears its own design.** Chapters with `cssclasses` take their vault snippet in full: `@font-face` now survives the snippet sanitizer when (and only when) its src is a font in the vault's own `.obsidian/fonts`, served over the vault scheme with `font-src` opened to exactly that. Rendered pages also carry Obsidian's `.markdown-preview-section` structure, so snippets written against Obsidian's preview DOM — drop caps included — apply verbatim. The desk behind the page is tinted from the book's declared paper color.
- Books without a stylesheet get a built-in treatment: justified serif at reading size, a drop cap, centered chapter titles, asterism scene breaks.

## 1.9.0 — 2026-09-02

Mermaid diagrams render — and note content still never executes.

- **Flowcharts, sequence diagrams, and pies draw as static SVG**, laid out by a pure-Python engine: node shapes (rectangles, rounded, stadium, circle, diamond, hexagon, cylinder, subroutine, flag), dotted/thick/bidirectional edges with labels, chained statements, subgraphs with titles, `style`/`classDef`/`:::class` stroke styling, quoted labels spanning lines, `<br/>` line breaks; lifelines, dashed replies, self-messages, notes and loop/alt bands; pie slices with a legend. Measured against this vault: **815 of 833 real blocks render (97.8%)** — the other 18 are gantt/state/timeline/xychart/er, which show as labeled source naming the kind.
- Layout does the unglamorous work: ranks ignore cycle-closing edges, gaps widen for the labels that cross them, co-located labels stagger, reverse edge pairs bow apart, and labels layer above every line.
- The sanitizer gained a scoped SVG allowlist (geometry and presentation attributes only, colors and paths pattern-checked); mermaid source is parsed as data and mermaid.js is never involved, so the no-JavaScript promise holds unchanged.
- `READER_MAX_DIAGRAM_NODES` (400) bounds hostile input like every other renderer.

## 1.8.1 — 2026-09-02

- **The outline lives in the right panel only.** The sidebar's Outline page shipped with a serious defect, and rather than patching around it the page is removed — along with the Outline Position option and the side-switching it required. `F8` and the header button toggle the right panel, which keeps its close button, its styling, and its memory. A smoke check now asserts the rail carries no outline page.

## 1.8.0 — 2026-09-02

One outline, on the side you choose.

- **The outline never shows in two places.** Opening the right panel switches the rail off its Outline page; picking the rail's Outline page collapses the panel. View → Outline Position chooses which side `F8` and the header button open — Left Sidebar or Right Panel — and changing it moves an open outline across immediately.
- **The rail outline dresses for the rail.** A gold OUTLINE heading, muted entries with a visible hierarchy — top-level headings bright and semibold, deeper levels dimmer and smaller — and gold on hover, instead of the plain text dump it launched as. The right panel picks up the same level hierarchy in its serif.

## 1.7.0 — 2026-09-02

Sidebar structure, on request.

- **Pinned & recent is a section now, and collapsible.** A disclosure on its label folds it away (remembered), a separator and a FOLDERS label separate it from the tree — no more two lists running into each other.
- **The outline can live in the rail too.** A seventh sidebar page shows the current note's headings on the left, mirroring the right panel — use whichever side suits the note, or both.
- **The tags and graph icons are visible again.** The custom bundled icons were never treated as symbolic by GTK, so they drew their baked dark gray — invisible on the dark rail. Replaced with the theme's own recolorable icons (a smoke check now asserts both stay symbolic).

## 1.6.1 — 2026-09-02

- **The outline panel matches the interface now.** It sits on a warm card surface in the canvas family, its label in the identity's gold, its entries in muted serif that answer in lapis on hover — instead of the stock widget styling it launched with.

## 1.6.0 — 2026-09-02

The two-surface release: depth instead of tint.

- **The sidebar is a rail now.** A deep sepia surface running the full height of the window — the vault's name in gold small caps at its top, the section switcher under it, gold selection with an accent bar, tinted icons, dark-styled search fields, and the note/tag count at its foot. Against the parchment canvas the window finally has fore- and background instead of one beige sheet. It still resizes by its divider and still hides with F9.
- **The header belongs to the content.** It sits flat on the canvas beside the rail rather than spanning the window as a third tint.
- **The note title never doubles and never goes missing.** When a note opens with an H1 repeating its filename, the body's copy yields to the header title — so every note starts the same way: breadcrumb, serif title with its gold rule, metadata line. (Previously the header title was suppressed instead, leaving the metadata line floating alone above the properties panel.)
- The local-graph pane draws in the identity's gold, and the outline panel keeps its place on the content side.

## 1.5.0 — 2026-09-02

The UX pass: every surface gets an obvious control, and the one element without one is gone.

- **The outline is a real panel now.** The floating "On this page" rail — which overlapped content and had no way to close it — is removed. In its place: a native outline panel docked on the right, with a visible toggle in the header (`F8`), its own close button, animated reveal, heading hierarchy, an empty state, and a memory of whether you keep it open. It replaces the cramped header popover too.
- **The header bar says what it does.** A sidebar toggle now sits at the far left (`F9` still works); the right side is search, outline, menu. The wide Read-only pill shrinks to a quiet lock icon — the explanation and its next actions (view source, open in editor, reveal in Files) are still one click away.
- Reading mode hides the outline panel with everything else and restores it on exit; the outline state, like every other panel, persists across sessions.
- View → Note Context now lists exactly the three elements that live in the page: Title & Breadcrumb, Metadata Line, Linked Mentions.

## 1.4.0 — 2026-09-02

The atelier redesign: one visual identity across the whole app, and every piece of it under the reader's control.

- **A manuscript identity.** The reading canvas wears parchment and sepia ink with lapis links and gold ornament by day, a candlelit nocturne by night. Serif display type carries titles and headings, the note title gets a short gold rule, section breaks render as a fleuron, blockquotes open with a proper quotation mark, and the app icon is retinted to match.
- **The chrome wears the same palettes.** The GTK window — sidebar, header bar, popovers, dialogs — is themed to the exact colors of the reading canvas in both light and dark, so the window and the page read as one surface instead of a browser in a frame. The header title is set in the display serif; a system light/dark flip re-tints the chrome and re-renders every open page together.
- **A real welcome page.** The app opens on a frontispiece: the mark, the name, two action cards, in-app documentation links, and recent vaults as cards — not a bare paragraph.
- **Note context is a choice, not a fixture.** View → Note Context toggles Title & Breadcrumb, the Metadata Line, the On This Page rail, and Linked Mentions individually — persisted, applied to every tab at once. The rail can now simply be switched off.
- Syntax-highlighted code blocks sit on the page's own surface in both themes (Pygments used to force its own panel color), and callout tints are softened to sit quietly on the warm background.

## 1.3.0 — 2026-09-02

The look-and-feel release: editorial rather than dashboard-like, with context before content.

- **Every note opens with its context.** A clickable breadcrumb above the title (each ancestor reveals its folder in the tree), an inline title when the body does not start with one, and a quiet metadata line — updated date, word count, read time on longer notes, and clickable tag chips that run a tag search.
- **An "On this page" rail** lists the note's headings beside the text on windows wide enough to hold it — fixed, scrollable, and gone in print. It steps aside when the line width is set to Wide or Full.
- **Linked mentions follow the content.** Notes that link to the current one are listed after it, collapsed, each with the line of context around the mention; the Links panel still carries the full list.
- **The reading canvas is editorial now**: a warm paper background with charcoal ink and one cobalt accent, 17px body text on a 65–80 character measure, callouts as tinted surfaces with a colored left edge instead of full colored boxes, tables ruled horizontally with a firmer line under the header, and consistent 8px-scale radii.
- **The read-only badge explains itself.** Clicking it says why the app cannot edit — by design, not by permission — and offers the next action: view raw source, open in the default editor, or reveal in Files.
- **Pinned & recent sits above the file tree.** Note menu → Pin/Unpin Note keeps a note at the top of the Files page; the five most recent notes follow. Selected sidebar rows now carry a left accent marker, not contrast alone.

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

- On stock Ubuntu 24.04+ the app could not start from a normal terminal: the kernel's unprivileged-user-namespace restriction blocks WebKit's bubblewrap sandbox (`bwrap: setting up uid map: Permission denied`). The launcher now preflights this before WebKit crashes and prints the fix — a rendered AppArmor profile granting `userns` to this app's interpreter alone, kept narrow by `make install` giving the venv a private interpreter copy. `SOLANDER_SKIP_SANDBOX_CHECK=1` bypasses the check.
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
