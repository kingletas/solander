"""The CSS snippet sanitizer: what survives, and what can never."""

import json

from obsidian_reader.core.csssnippets import load_snippets, sanitize_css


def test_plain_rules_and_media_blocks_survive():
    css = sanitize_css(
        "/* c */ .red-ink { color: red; }\n@media print { .x { display: none; } }"
    )
    assert ".red-ink { color: red; }" in css
    assert "@media print" in css and "display: none" in css


def test_network_and_escape_vectors_are_dropped():
    hostile = (
        '.a { background: url("http://evil/x.png"); color: blue; }\n'
        "@import url(http://evil/style.css);\n"
        '.b { behavior: expression(alert(1)); }\n'
        ".c { content: '\\75 rl(x)'; }\n"
        "@font-face { src: url(http://evil/f.woff); }\n"
    )
    css = sanitize_css(hostile)
    assert "url(" not in css.casefold()
    assert "@import" not in css
    assert "expression" not in css
    assert "\\" not in css
    assert "@font-face" not in css
    assert "color: blue" in css


def test_loader_honors_the_enabled_list(tmp_path):
    obsidian = tmp_path / ".obsidian"
    (obsidian / "snippets").mkdir(parents=True)
    (obsidian / "snippets" / "on.css").write_text(".on { color: green; }")
    (obsidian / "snippets" / "off.css").write_text(".off { color: red; }")
    (obsidian / "appearance.json").write_text(
        json.dumps({"enabledCssSnippets": ["on", "on.css", "../escape"]})
    )
    css = load_snippets(tmp_path)
    assert ".on" in css
    assert ".off" not in css


def test_no_appearance_file_means_no_css(tmp_path):
    assert load_snippets(tmp_path) == ""
