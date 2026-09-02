"""Loads the vault's enabled CSS snippets through a strict sanitizer, read-only.

Snippet CSS is vault content and therefore untrusted. The sanitizer is an
allowlist by construction: comments are stripped, only plain rules and @media
blocks survive, and any declaration that could reach the network or smuggle an
escape — url(), @import, expression(), a backslash — is dropped whole.
"""

import json
import os
import re
from pathlib import Path
from urllib.parse import quote

MAX_SNIPPET_BYTES = int(os.environ.get("READER_MAX_SNIPPET_BYTES", str(256 * 1024)))

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_DANGEROUS = re.compile(r"url\s*\(|expression\s*\(|@import|javascript:|\\|</", re.IGNORECASE)

# The one url() that survives: a vault-local font file, rewritten to the vault
# scheme so @font-face works while the network stays unreachable.
_FONT_DECLARATIONS = {"font-family", "font-weight", "font-style", "font-display", "src"}
_FONT_SRC = re.compile(
    r"""^url\(\s*["']?(?:\.\./)?fonts/(?P<name>[\w\[\],. -]{1,80}\.(?:ttf|otf|woff2?))["']?\s*\)
    (?:\s*format\(["'][\w-]{1,20}["']\))?$""",
    re.X | re.IGNORECASE,
)


def load_snippets(root: Path) -> str:
    """Returns the sanitized CSS of every snippet the vault has enabled."""
    obsidian = root / ".obsidian"
    try:
        appearance = json.loads((obsidian / "appearance.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    enabled = appearance.get("enabledCssSnippets")
    if not isinstance(enabled, list):
        return ""
    pieces = []
    total = 0
    seen = set()
    for name in enabled:
        if not isinstance(name, str):
            continue
        stem = name.removesuffix(".css")
        if not re.fullmatch(r"[\w .-]+", stem) or stem in seen:
            continue
        seen.add(stem)
        path = obsidian / "snippets" / f"{stem}.css"
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        total += len(raw)
        if total > MAX_SNIPPET_BYTES:
            break
        pieces.append(sanitize_css(raw))
    return "\n".join(piece for piece in pieces if piece)


def sanitize_css(text: str) -> str:
    """Reduces a stylesheet to plain rules and @media blocks with safe declarations."""
    return "".join(_safe_rules(_COMMENT.sub("", text)))


def _safe_rules(text: str):
    position = 0
    while position < len(text):
        brace = text.find("{", position)
        if brace < 0:
            return
        selector = text[position:brace].strip()
        block, position = _read_block(text, brace)
        if not selector:
            continue
        if selector.startswith("@"):
            if selector.casefold().startswith("@media") and "\\" not in selector:
                inner = "".join(_safe_rules(block))
                if inner:
                    yield f"{selector} {{ {inner} }}\n"
            elif selector.casefold() == "@font-face":
                rule = _font_face_rule(block)
                if rule:
                    yield rule
            continue
        if _DANGEROUS.search(selector) or "{" in block:
            continue
        declarations = [
            part.strip()
            for part in block.split(";")
            if part.strip() and not _DANGEROUS.search(part)
        ]
        if declarations:
            yield f"{selector} {{ {'; '.join(declarations)}; }}\n"


def _font_face_rule(block: str) -> str:
    """Rebuilds a @font-face whose src is a vault font file; anything else is dropped."""
    if "{" in block:
        return ""
    kept = []
    for part in block.split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        name, _, value = part.partition(":")
        name = name.strip().casefold()
        value = value.strip()
        if name not in _FONT_DECLARATIONS:
            return ""
        if name == "src":
            src = _FONT_SRC.match(value)
            if not src:
                return ""
            value = f'url("vault:///.obsidian/fonts/{quote(src.group("name"), safe="")}")'
        elif _DANGEROUS.search(part):
            return ""
        kept.append(f"{name}: {value}")
    if not any(part.startswith("src:") for part in kept):
        return ""
    return f"@font-face {{ {'; '.join(kept)}; }}\n"


def _read_block(text: str, brace: int) -> tuple[str, int]:
    """Returns the balanced content of the block opening at `brace`, and the resume point."""
    depth = 0
    for position in range(brace, len(text)):
        if text[position] == "{":
            depth += 1
        elif text[position] == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1 : position], position + 1
    return text[brace + 1 :], len(text)
