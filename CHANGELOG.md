# Changelog

## 0.1.0 — 2026-09-01

First release. A read-only GTK4/libadwaita reader for Obsidian vaults.

- Opens a folder as a vault or a single note, in place, from the CLI, the file dialogs, drag-and-drop, or a recent-vaults list; a second launch hands its path to the running instance.
- Renders CommonMark and GFM plus the Obsidian layer: wikilinks with aliases, heading and block links, note/section/block embeds with cycle detection and a depth limit, callouts (foldable and nested), highlights, hidden comments (`%%` and HTML), inline tags, extended task states, footnotes (inline included), frontmatter as a collapsible Properties panel, image sizing syntax, and syntax-highlighted code.
- Resolves links path-first then by filename; ambiguous names open a chooser, never an arbitrary note; missing links are visibly marked.
- Vault-wide filename and full-text search with snippets, in-note find, back/forward history, outline navigation, light/dark/system appearance, zoom, session restore, and a read-only indicator.
- Security: JavaScript disabled in the rendering surface, raw note HTML escaped, generated HTML passed through an allowlist sanitizer, assets served only through a vault-contained URI scheme, remote resources blocked, `http`/`https` links handed to the system browser, every other scheme refused. Dataview/Templater/mermaid blocks render as labeled inert source.
- Zero-write guarantee covered by a test that hashes a vault before and after a full index-and-render pass; the full suite is 71 tests plus a scripted GUI smoke run.
