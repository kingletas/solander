# Security

## Model

The reader treats every vault as attacker-controlled input. The load-bearing controls, each covered by a test in `tests/`:

- **No script execution.** JavaScript is disabled at the WebKit settings level, and the app refuses to start if those settings do not exist. Raw HTML in notes is escaped by the parser, and the generated markup passes an allowlist sanitizer before display.
- **No network.** Remote images, stylesheets, fonts, and frames are blocked by the sanitizer, the page CSP, and the navigation policy. `http`/`https` links open in the system browser; every other scheme is refused.
- **Vault containment.** Assets are served only through a `vault:` URI scheme whose handler refuses any path — symlinks included — that resolves outside the vault root.
- **No writes.** The application never writes below a vault root; a test hashes a vault tree before and after a full index-and-render pass and asserts byte identity.
- **Bounded resources.** Note size, frontmatter size, embed depth, and embeds-per-page are all capped; YAML aliases in frontmatter are refused outright.

## Reporting a vulnerability

Email **code@kingletas.com** with a description and, ideally, a minimal vault that reproduces the issue. You will get an acknowledgment, a triage verdict, and — for confirmed issues — a fix accompanied by a regression test and a sweep for the rest of the defect's class.
