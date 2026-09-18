# Why Solander exists

**Because the only program that reads an Obsidian vault properly is Obsidian, and there are a lot of moments when that is the wrong program to open.**

## The problem

A vault is not a folder of Markdown. It is a folder of Markdown plus a dialect — wikilinks, embeds, callouts, frontmatter properties, tags, canvases, kanban boards, `.base` views, Dataview queries. Open one of those notes in a general Markdown viewer and you get `[[Some Note]]` printed as four brackets and a name, a callout rendered as a blockquote with a stray `[!warning]` in it, and a Dataview block shown as an unrun code fence. The notes are there and the vault is not.

So the practical answer has always been "just open Obsidian". That answer runs out in ordinary situations:

- Obsidian is closed, updating, or has crashed.
- You are on a machine that does not have it, and installing an Electron editor to read a file is not proportionate.
- The vault is not yours. Somebody handed you an archive and you want to look at it, not adopt it.

## Why not just open Obsidian anyway

Because opening it writes. Workspace state, index caches, plugin data, `.obsidian` settings — an editor keeps its own records, which is correct behaviour for an editor. It is the wrong behaviour for something you only mean to inspect. A vault you open to look at should be byte-identical when you close it, and nothing that can write can promise that.

Obsidian also runs the vault's plugins. A vault is executable content, and there are vaults you would rather read than run.

## Why not a generic Markdown viewer

They render CommonMark, and CommonMark is the part of a vault that was never the problem. The dialect is the whole reason a vault is more useful than a folder, and no general viewer implements it — resolution order for an ambiguous wikilink, an embed with a heading fragment, a callout that folds, a `.base` table, a Dataview query that has to be evaluated against an index of the whole vault.

## What the reason decided

Every hard rule in this application comes back to that paragraph, which is why they are worth keeping even when they are inconvenient:

- **It never writes into the vault.** Not a cache, not an index, not a dotfile. The index lives outside the vault, per vault. A before-and-after hash test holds this on every commit rather than a sentence in a README.
- **It never executes anything the vault contains.** JavaScript is off in the web view, and the application refuses to start if it cannot be turned off. Dataview is evaluated in Python by us, not by running the vault's code.
- **It never opens a network connection.** Remote loads are blocked at the renderer.
- **It reads, and it does not edit.** An editor is a different product with a different promise. That is Slate's problem, not this one's.

## Where the name came from

A solander is the clamshell box an archive keeps its documents in — a hinged case, made to the size of what it holds, that you open to look at a thing and close to leave it as it was. That is the design brief in one object, which is why the application is not named after the format it reads.
