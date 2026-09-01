"""Allowlist HTML sanitizer: the last pass before markup reaches the rendering surface."""

import html
import re
from html.parser import HTMLParser
from io import StringIO

ALLOWED_TAGS = {
    "a", "aside", "audio", "blockquote", "br", "caption", "code", "dd", "del", "details",
    "div", "dl", "dt", "em", "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "img", "input", "li", "mark", "ol", "p", "pre", "s", "section", "source", "span",
    "strong", "sub", "summary", "sup", "table", "tbody", "td", "th", "thead", "tr", "ul",
    "video",
}

# MathML as latex2mathml emits it; WebKit renders these natively, scripts cannot
# hide in them, and every attribute below is presentational.
MATHML_TAGS = {
    "math", "annotation", "menclose", "mfenced", "mfrac", "mi", "mn", "mo", "mover",
    "mpadded", "mphantom", "mroot", "mrow", "mspace", "msqrt", "mstyle", "msub", "msubsup",
    "msup", "mtable", "mtd", "mtext", "mtr", "munder", "munderover", "semantics",
}
ALLOWED_TAGS |= MATHML_TAGS

_MATHML_ATTRIBUTES = {
    "math": {"xmlns", "display"},
    "annotation": {"encoding"},
    "mo": {"stretchy", "fence", "separator", "form", "lspace", "rspace"},
    "mspace": {"width", "height", "depth"},
    "mstyle": {"displaystyle", "scriptlevel", "mathsize"},
    "mfrac": {"linethickness"},
    "mtable": {"columnalign", "rowalign", "columnspacing", "rowspacing"},
    "mtd": {"columnalign", "rowalign"},
    "mtr": {"columnalign", "rowalign"},
    "mpadded": {"width", "height", "depth", "lspace", "voffset"},
    "menclose": {"notation"},
    "mi": {"mathvariant"},
    "mtext": {"mathvariant"},
}

VOID_TAGS = {"br", "hr", "img", "input", "source"}

# Content inside these is dangerous even as text-adjacent markup and is removed whole.
DROPPED_WITH_CONTENT = {"script", "style", "iframe", "object", "embed", "template", "noscript"}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "class", "title", "id"},
    "audio": {"src", "controls", "class"},
    "video": {"src", "controls", "class", "width", "height"},
    "source": {"src", "type"},
    "img": {"src", "alt", "title", "class", "width", "height"},
    "input": {"type", "checked", "disabled", "class"},
    "details": {"class", "open", "data-callout"},
    "div": {"class", "id", "data-callout"},
    "span": {"class", "id"},
    "li": {"class", "id"},
    "ol": {"class", "start"},
    "td": {"style", "class"},
    "th": {"style", "class"},
    "code": {"class"},
    "pre": {"class"},
    "h1": {"id"}, "h2": {"id"}, "h3": {"id"}, "h4": {"id"}, "h5": {"id"}, "h6": {"id"},
    "section": {"class", "id"},
    "sup": {"class", "id"},
    "sub": {"class", "id"},
    "table": {"class"},
    "blockquote": {"class"},
    "summary": {"class"},
    "mark": {"class"},
    "p": {"class"},
    "figure": {"class"},
    "figcaption": {"class"},
    "aside": {"class"},
}
ALLOWED_ATTRIBUTES.update(_MATHML_ATTRIBUTES)

# Internal pages, vault assets, and browser-bound links; nothing else survives.
ALLOWED_LINK_SCHEMES = ("reader:", "vault:", "http:", "https:", "mailto:")
ALLOWED_MEDIA_SCHEMES = ("vault:",)

_SAFE_STYLE = re.compile(r"^text-align\s*:\s*(left|right|center|justify)\s*;?$")
_SAFE_DIMENSION = re.compile(r"^\d{1,5}$")
_SAFE_LENGTH = re.compile(r"^-?\d{0,4}(\.\d{1,4})?(em|ex|px|pt|%)?$")


def _safe_url(value: str, schemes: tuple[str, ...]) -> str:
    """Returns the URL unchanged when its scheme is allowed, empty otherwise."""
    stripped = value.strip()
    if stripped.startswith("#"):
        return stripped
    lowered = stripped.casefold()
    for scheme in schemes:
        if lowered.startswith(scheme):
            return stripped
    return ""


class _Sanitizer(HTMLParser):
    """Streams input markup back out with everything off the allowlist removed."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output = StringIO()
        self.suppressed = 0

    def _filter_attributes(self, tag: str, attrs: list) -> str:
        allowed = ALLOWED_ATTRIBUTES.get(tag, set())
        pieces = []
        for name, value in attrs:
            name = name.casefold()
            if name not in allowed:
                continue
            value = value or ""
            if name in ("href",):
                value = _safe_url(value, ALLOWED_LINK_SCHEMES)
                if not value:
                    continue
            elif name == "src":
                value = _safe_url(value, ALLOWED_MEDIA_SCHEMES)
                if not value:
                    continue
            elif name == "style":
                if not _SAFE_STYLE.match(value):
                    continue
            elif name in ("width", "height", "start"):
                pattern = _SAFE_LENGTH if tag in MATHML_TAGS else _SAFE_DIMENSION
                if not pattern.match(value):
                    continue
            elif name == "type" and tag == "input":
                if value != "checkbox":
                    continue
            if name in ("checked", "disabled", "open", "controls"):
                pieces.append(f" {name}")
            else:
                pieces.append(f' {name}="{html.escape(value, quote=True)}"')
        return "".join(pieces)

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if self.suppressed:
            if tag in DROPPED_WITH_CONTENT and tag not in VOID_TAGS:
                self.suppressed += 1
            return
        if tag in DROPPED_WITH_CONTENT:
            self.suppressed = 1
            return
        if tag not in ALLOWED_TAGS:
            return
        closing = " /" if tag in VOID_TAGS else ""
        self.output.write(f"<{tag}{self._filter_attributes(tag, attrs)}{closing}>")

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        if self.suppressed or tag in DROPPED_WITH_CONTENT or tag not in ALLOWED_TAGS:
            return
        self.output.write(f"<{tag}{self._filter_attributes(tag, attrs)} />")

    def handle_endtag(self, tag: str) -> None:
        if self.suppressed:
            if tag in DROPPED_WITH_CONTENT:
                self.suppressed -= 1
            return
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self.output.write(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.output.write(html.escape(data))


def sanitize(markup: str) -> str:
    """Reduces markup to the allowlisted subset; everything else is stripped or escaped."""
    sanitizer = _Sanitizer()
    sanitizer.feed(markup)
    sanitizer.close()
    return sanitizer.output.getvalue()
