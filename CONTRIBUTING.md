# Contributing

Thanks for looking. This is a small, opinionated application, and the constraints below are the point of it rather than obstacles to work around.

## The three promises

Every change is measured against these before anything else:

1. **It never writes into the vault.** No caches, indexes, locks, conflict files or thumbnails. All state lives under `~/.config/solander/` and `~/.cache/solander/`. There is a test that hashes a fixture vault before and after a full index-and-render pass and fails on any difference — if your change makes that test hard to pass, the change is wrong, not the test.
2. **It never executes anything a vault contains.** JavaScript is off in the rendering surface and the app refuses to start if it cannot be. Anything requiring execution — `dataviewjs`, Templater — renders as labeled inert source. Features that would need a script engine are declined rather than sandboxed.
3. **It never touches the network.** Remote images, scripts, stylesheets and fonts are blocked. `http`/`https` links open in the system browser; every other URI scheme is refused.

A pull request that relaxes one of these needs to argue the case in the issue first — it will usually be a no.

## Setting up

Ubuntu 24.04+, the system GObject bindings, and [uv](https://docs.astral.sh/uv/):

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0
```

```bash
make sync
```

`make sync` builds the virtualenv **against the system Python** with `--system-site-packages`, which is what makes the GI bindings visible. A virtualenv built any other way cannot import `gi` and the app will not start.

## Running the checks

```bash
make check
```

That is ruff, the test suite and the metadata validation, and it is exactly what the pre-commit hook runs. All three must be clean. The metadata step checks the desktop entry and the AppStream metainfo — the two files a software centre reads, which nothing else exercises; it degrades to a visible skip if `desktop-file-utils` and `appstream` are not installed, and CI installs both so it always runs there.

```bash
make smoke
```

The smoke run drives the **real window on a live display** through open, render, search, navigation, themes, book mode and PDF export — over a hundred assertions against a temporary fixture vault. It needs a desktop session. The GTK and WebKit layer has no unit tests by design; this is what covers it.

## How the code is arranged

- `src/solander/core/` — the vault model, link resolution, Markdown transforms, the sanitizer, search, Dataview, the renderers. **Pure Python, no GTK import anywhere.** This is where the tests live, and where a new feature usually belongs.
- `src/solander/gui/` — the GTK and WebKit layer, kept deliberately thin: it wires widgets to core functions and owns no rendering logic.
- `src/solander/assets/` — the stylesheet, the theme stylesheet, the app mark.
- `scripts/` — the smoke run and the two acceptance harnesses (Dataview, mermaid) that measure coverage against a real vault.

## Conventions worth knowing before you write

- **The sanitizer is the trust boundary.** Everything upstream of it handles attacker-controlled text; nothing downstream may receive unsanitized markup. New markup goes through it, or is app-authored with forced escaping and allowlisted values.
- **Unsupported degrades visibly.** Anything the app cannot render becomes labeled source that names the reason. Silently dropping content is a bug.
- **A theme is a palette, not a stylesheet.** Adding one to the Archive family means one entry in `core/palettes.py`; the tokens, the window chrome and the syntax colours are generated from it. Every colour that carries text is asserted against WCAG AA on the ground it sits on.
- **Bounds are tested with the payload that broke things.** Note size, frontmatter size, embed depth and embeds per page are all capped, and each cap has a test built from input that previously froze the renderer.
- **Comments say what the code does or what it guards against**, in a sentence or two. History belongs in the commit message and the changelog.

## Sending a change

- One concern per pull request, with the reasoning in the description.
- `make check` green, and `make smoke` green if you touched the GTK layer.
- A test with the fix. For a rendering bug, the fixture note that reproduced it.
- Add your entry to `CHANGELOG.md` under `## Unreleased`, in the voice of the entries already there: what changed for someone using it, not what the diff did.

## Releasing

The version is declared once, as `__version__` in `src/solander/__init__.py`. `pyproject.toml` reads it from there, `packaging/version.sh` is what everything outside Python asks, and the install commands in the documentation take a glob rather than naming a version.

```bash
make release VERSION=2.2.5
```

That writes the version, retitles the `## Unreleased` changelog section with today's date, and adds the AppStream entry a software centre reads. It seeds that entry's description with a placeholder, which `make check` refuses — the paragraph a software centre shows is the one thing here no script can write. Add `DRY_RUN=1` to see what it would change.

Then `make check`, commit, and tag: pushing a `v*` tag is the whole release trigger, and the release body is that version's changelog section.

## Security

Please do not open a public issue for a vulnerability. [SECURITY.md](SECURITY.md) has the threat model and the reporting route.
