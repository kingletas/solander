"""The sanitizer is the trust boundary; both directions get tested."""

from obsidian_reader.core.sanitize import sanitize


def test_allowed_markup_passes_through():
    markup = '<p>Hello <strong>world</strong> <a href="https://a.example">link</a></p>'
    assert sanitize(markup) == markup


def test_script_and_its_content_are_removed():
    assert sanitize("before<script>alert(1)</script>after") == "beforeafter"
    assert sanitize("<style>body{}</style>x") == "x"
    assert sanitize('<iframe src="https://a"></iframe>') == ""


def test_event_handlers_are_stripped():
    assert sanitize('<p onclick="evil()">hi</p>') == "<p>hi</p>"
    hardened = sanitize('<img src="vault:///a.png" onerror="evil()" />')
    assert hardened == '<img src="vault:///a.png" />'


def test_unsafe_url_schemes_are_dropped():
    assert 'href' not in sanitize('<a href="javascript:alert(1)">x</a>')
    assert 'href' not in sanitize('<a href="file:///etc/passwd">x</a>')
    assert 'src' not in sanitize('<img src="https://remote/x.png" />')
    assert 'src' not in sanitize('<img src="data:image/svg+xml,<svg/>" />')


def test_safe_url_schemes_survive():
    assert sanitize('<a href="reader:///note/A.md">x</a>') == '<a href="reader:///note/A.md">x</a>'
    assert sanitize('<a href="#anchor">x</a>') == '<a href="#anchor">x</a>'
    assert sanitize('<img src="vault:///a.png" />') == '<img src="vault:///a.png" />'


def test_unknown_tags_are_dropped_but_text_kept():
    assert sanitize("<blink>hi</blink>") == "hi"
    assert sanitize("<form><input type='text'></form>") == "<input />"


def test_style_attribute_is_restricted_to_alignment():
    aligned = sanitize('<td style="text-align:center">x</td>')
    assert aligned == '<td style="text-align:center">x</td>'
    assert "style" not in sanitize('<td style="background:url(https://x)">x</td>')


def test_dimensions_must_be_numeric():
    assert 'width="300"' in sanitize('<img src="vault:///a.png" width="300" />')
    assert "width" not in sanitize('<img src="vault:///a.png" width="30em" />')


def test_input_only_as_disabled_checkbox_shape():
    checkbox = sanitize('<input type="checkbox" checked disabled>')
    assert checkbox == '<input type="checkbox" checked disabled />'
    assert "type" not in sanitize('<input type="password">')


def test_text_content_is_escaped():
    assert sanitize("a < b & c") == "a &lt; b &amp; c"
