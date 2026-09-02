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

# SVG as the diagram renderers emit it: geometry and presentation only. Raw HTML
# in notes is escaped before this pass, so these tags only ever arrive from our
# own generators; the attribute patterns below are defense in depth.
SVG_TAGS = {
    "svg", "g", "rect", "circle", "ellipse", "line", "path", "polygon", "polyline",
    "text", "tspan", "defs", "marker",
}
ALLOWED_TAGS |= SVG_TAGS

_SVG_COMMON = {
    "class", "fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap",
    "stroke-linejoin", "opacity", "style",
}
_SVG_ATTRIBUTES = {
    "svg": _SVG_COMMON | {"xmlns", "viewbox", "width", "height", "role"},
    "g": _SVG_COMMON | {"transform"},
    "rect": _SVG_COMMON | {"x", "y", "width", "height", "rx", "ry"},
    "circle": _SVG_COMMON | {"cx", "cy", "r"},
    "ellipse": _SVG_COMMON | {"cx", "cy", "rx", "ry"},
    "line": _SVG_COMMON | {"x1", "y1", "x2", "y2", "marker-end", "marker-start"},
    "path": _SVG_COMMON | {"d", "marker-end", "marker-start"},
    "polygon": _SVG_COMMON | {"points"},
    "polyline": _SVG_COMMON | {"points", "marker-end"},
    "text": _SVG_COMMON | {
        "x", "y", "text-anchor", "font-size", "font-family", "font-weight",
        "dominant-baseline",
    },
    "tspan": _SVG_COMMON | {"x", "y", "dx", "dy"},
    "defs": set(),
    "marker": {
        "id", "viewbox", "refx", "refy", "markerwidth", "markerheight", "orient",
        "markerunits",
    },
}

_SVG_COLOR = re.compile(r"^(#[0-9a-fA-F]{3,8}|[a-zA-Z-]{1,24})$")
_SVG_NUMBERS = re.compile(r"^[0-9eE .,\-]{1,4000}$")
_SVG_PATH = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9eE .,\-]{1,8000}$")
_SVG_STYLE = re.compile(
    r"^(stroke|fill|stroke-width)\s*:\s*[#a-zA-Z0-9.]{1,24}"
    r"(;\s*(stroke|fill|stroke-width)\s*:\s*[#a-zA-Z0-9.]{1,24})*;?$"
)
_SVG_MARKER_REF = re.compile(r"^url\(#[A-Za-z0-9_-]{1,64}\)$")
_SVG_TRANSFORM = re.compile(r"^[a-z]+\([0-9eE .,\-]{1,200}\)( [a-z]+\([0-9eE .,\-]{1,200}\))*$")

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
ALLOWED_ATTRIBUTES.update(_SVG_ATTRIBUTES)

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
        svg = tag in SVG_TAGS
        pieces = []
        for name, value in attrs:
            name = name.casefold()
            if name not in allowed:
                continue
            value = value or ""
            if svg:
                if not self._svg_value_ok(name, value):
                    continue
                pieces.append(f' {name}="{html.escape(value, quote=True)}"')
                continue
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

    @staticmethod
    def _svg_value_ok(name: str, value: str) -> bool:
        """Per-attribute value patterns for the SVG the diagram renderers emit."""
        if name in ("fill", "stroke"):
            return bool(_SVG_COLOR.match(value))
        if name == "style":
            return bool(_SVG_STYLE.match(value))
        if name == "d":
            return bool(_SVG_PATH.match(value))
        if name in ("marker-end", "marker-start"):
            return bool(_SVG_MARKER_REF.match(value))
        if name == "transform":
            return bool(_SVG_TRANSFORM.match(value))
        if name == "xmlns":
            return value == "http://www.w3.org/2000/svg"
        if name in (
            "class", "id", "role", "text-anchor", "dominant-baseline", "font-family",
            "font-weight", "stroke-linecap", "stroke-linejoin", "orient", "markerunits",
        ):
            return bool(re.match(r"^[A-Za-z0-9 _,#()/-]{1,120}$", value))
        return bool(_SVG_NUMBERS.match(value))

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
