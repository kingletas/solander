# From nothing to reading a vault

By the end of this you'll have Solander installed, a vault open in it, and a clear idea of what it will and won't do to your files. It takes about ten minutes, and most of that is one download.

You don't need Obsidian. You don't need to have used a markdown reader before. A "vault" here is just a folder with markdown in it, and you'll make one in a minute.

## Contents

- [What this is, and what it refuses to do](#what-this-is-and-what-it-refuses-to-do)
- [Step 1: install it](#step-1-install-it)
- [Step 2: the sandbox, if you installed from source](#step-2-the-sandbox-if-you-installed-from-source)
- [Step 3: make a vault](#step-3-make-a-vault)
- [Step 4: open it](#step-4-open-it)
- [Step 5: find something](#step-5-find-something)
- [Make it comfortable](#make-it-comfortable)
- [What it understands](#what-it-understands)
- [Where your settings live](#where-your-settings-live)
- [When something is wrong](#when-something-is-wrong)
- [Where to go next](#where-to-go-next)

## What this is, and what it refuses to do

Suppose somebody sends you a folder of notes. Or you have an Obsidian vault and you want to read it on a machine where Obsidian isn't installed — or you'd rather not point a full editor at notes you only mean to look at.

You could open the files in a text editor. That works, and `[[Recipes]]` stays `[[Recipes]]`, a callout looks like a block quote with stray text on top, and a `.canvas` file is a wall of JSON.

Solander renders all of it, and **never writes into the folder**. That's the whole idea, and it's worth being precise about what it means:

- **No caches, no index files, no lock files, no thumbnails** land in your vault. Everything it remembers lives under `~/.config/solander/` and `~/.cache/solander/`.
- **Nothing in a note is executed.** JavaScript is off in the rendering surface, raw HTML is escaped, and Templater or `dataviewjs` blocks render as labelled inert source rather than running.
- **It doesn't touch the network.** Remote images, scripts, stylesheets and fonts are blocked. An `http` link opens in your normal browser; any other URI scheme is refused.

A solander is the clamshell box an archive keeps documents in — you open it to look at something and close it to leave it as it was. That's the design brief in one object.

## Step 1: install it

Three routes. **If you're not sure, take the Flatpak** — it's the only one with no sandbox step at all.

### Flatpak, the simplest

The bundle doesn't carry the GNOME runtime it needs, so you need a remote that provides one. If you've ever installed anything from Flathub, you already have it:

```bash
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

Then take the bundle from the [latest release](https://github.com/kingletas/solander/releases/latest) and install it:

```bash
flatpak install --user solander_*.flatpak
```

The first install also pulls the runtime — about a gigabyte, once, shared with every other Flatpak you ever install. **A Flatpak install puts no `solander` on your `PATH`**; the terminal equivalent is `flatpak run com.kingletas.Solander`.

### Debian package

Ubuntu 24.04 or newer. It pulls the GObject bindings itself and installs the sandbox profile, so there's nothing to do afterwards:

```bash
sudo apt install ./solander_*_all.deb
```

### From source

You'll need the system GObject bindings, because these can't come from a virtualenv:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0
```

Then, with [uv](https://docs.astral.sh/uv/) installed:

```bash
make install
```

That builds a virtualenv against the system Python so the bindings are visible, and puts a `solander` launcher on your `PATH`. **A source install needs the one-time sandbox step below.** The Flatpak and the deb don't.

Whichever route you took:

```bash
solander --version
```

```text
solander 2.3.0
```

## Step 2: the sandbox, if you installed from source

Skip this if you used the Flatpak or the deb. They handle it.

**Here's the part that surprises people.** WebKit — the thing that draws your notes — wraps its rendering processes in a sandbox of its own, and that sandbox needs to create an unprivileged user namespace. Ubuntu 24.04 restricts those by default. So on a stock Ubuntu the app would abort with `bwrap: setting up uid map: Permission denied`, which tells you nothing useful.

Solander checks for this **before** WebKit crashes. Started from your applications grid, it opens a small setup window with one command to copy and a *check again* button. Started from a terminal, it prints the same fix.

The fix is a one-time AppArmor profile granting that permission to this app's interpreter and nothing else:

```bash
solander --sandbox | sudo tee /etc/apparmor.d/solander
```

```bash
sudo apparmor_parser -r /etc/apparmor.d/solander
```

```bash
solander --sandbox-status
```

```text
profile     /etc/apparmor.d/solander installed
interpreter /home/you/…/.venv/bin/python
label       solander (unconfined)
sandbox     works
```

That last command exits non-zero while anything is still wrong, so it's the one to trust rather than "it seemed to start".

**This keeps WebKit's own sandbox on**, which is why it's the right fix rather than turning off user-namespace restrictions for your whole system. It's the same mechanism Ubuntu ships for browsers.

> [!NOTE]
> Start the app through the `solander` launcher, not by running the virtualenv's script directly. AppArmor attaches a profile by interpreter path, and a `#!` launch bypasses that attachment. The launcher execs the interpreter directly for exactly this reason.

## Step 3: make a vault

A vault is a folder with markdown in it. Nothing else is required — no config file, no hidden directory, no Obsidian.

```bash
mkdir -p ~/first-vault
```

Put this in `~/first-vault/Welcome.md`:

```markdown
---
tags: [start]
---

# Welcome

This is a vault. It's just a folder with markdown in it.

A link to [[Recipes]] resolves by name, the way Obsidian does it.

> [!tip] Callouts render as callouts
> Not as a block quote with stray text at the top.
```

And this in `~/first-vault/Recipes.md`:

```markdown
# Recipes

Back to [[Welcome]].

| Dish | Time |
| --- | --- |
| Soup | 20m |
```

Two files. That's a vault.

## Step 4: open it

```bash
solander ~/first-vault
```

The window opens on the vault. Click through to **Recipes** and back — `[[Welcome]]` and `[[Recipes]]` resolve to each other by name, the table is a table, and the tip is a callout with its own colour rather than a quote with the word "tip" stuck on the front.

Three other ways in, all equivalent:

```bash
solander note.md              # a single note, without its folder
```

```bash
solander                      # reopen whatever you had last
```

Or launch **Solander** from your applications grid, which restores your last session. Markdown files and folders also offer it under *Open With* in your file manager.

**Opening it a second time hands the path to the window that's already running** rather than racing it for your settings.

## Step 5: find something

Two notes don't need finding. Ten thousand do, and this is where a reader earns its keep.

- **Quick open** is fuzzy: type part of a name and it ranks by how the query matched, not just whether it did.
- **Search** is full text, ranked by relevance, with hits highlighted in place. It takes `path:`, `file:` and `tag:` operators, so `tag:recipe soup` means what you'd expect.
- **Backlinks** show every note pointing at this one, with the sentence around each link rather than a bare list.
- There's a **tag browser**, your vault's own **bookmarks**, a **local graph**, and hover previews on links.

**The index is built once per vault and kept**, so a ten-thousand-note vault opens in about a second after its first build. The folder is watched too — edit a note in another program and the change appears in seconds.

## Make it comfortable

Fourteen themes, and the one you pick is remembered. **Atelier** is the default: parchment and sepia by day, a candlelit version after dark. The **Archive** family is thirteen dark themes over one design language, and the meanings hold across all of them — danger, warning, verified and information look like themselves in every one.

Beyond that: tabs, an outline panel (`F8`), reading mode, typography controls, pinned notes, a mind-map view of any note, your vault's own CSS snippets (sanitized first), folder hiding, and PDF export through a real print stylesheet.

## What it understands

CommonMark and GitHub-flavoured markdown, plus the Obsidian layer: wikilinks with Obsidian's own resolution order, embeds, callouts, highlights, comments, tags, footnotes, frontmatter properties and syntax-highlighted code.

Then the parts people assume a reader will skip:

- **TeX maths** as native MathML.
- **`.canvas` files** as canvases.
- **Kanban boards** as boards.
- **Excalidraw drawings** as SVG.
- **`.base` files** as table views.
- **Dataview queries and inline expressions**, evaluated in pure Python against the live index.

**Anything it can't render degrades to labelled source with the reason**, rather than to a blank space or a stack trace.

## Where your settings live

Nothing in your vault. Two directories, both yours to delete:

| | |
|---|---|
| `~/.config/solander/` | Your session — last vault, last note, theme, pinned notes, hidden folders |
| `~/.cache/solander/` | The per-vault index, which is what makes the second open fast |

Delete either and you lose convenience, never content.

## When something is wrong

**It refuses to start and mentions `bwrap` or a sandbox.** Step 2. Run `solander --sandbox-status` and it will tell you which part isn't in place.

**It says it needs the system GTK bindings.** The `apt install` line in step 1 — these can't come from a virtualenv, which is why the source install asks for them separately.

**A note renders as labelled source.** That's deliberate, and the label says why. Something in it isn't supported, or is something we won't execute.

**Something looks wrong in the rendering.** It's a reader, so the worst case is that it looks wrong — your files are untouched. Open an issue with the note that did it.

## Where to go next

- [Getting started](getting-started.md) — the short version of installing
- [User guide](user-guide.md) — every view and every key
- [README](../README.md) — what it is, in one page
- [SECURITY.md](../SECURITY.md) — the model, and where to report something
