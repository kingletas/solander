"""Pure-Python rendering for the Mermaid diagrams this vault actually writes.

Flowcharts, sequence diagrams, and pies cover ~98% of the corpus; anything else
raises MermaidUnsupported and renders as labeled source. Nothing here executes
note content — the source is parsed as data and drawn as static SVG.
"""

import html
import math
import os
import re
from dataclasses import dataclass, field

MAX_DIAGRAM_NODES = int(os.environ.get("READER_MAX_DIAGRAM_NODES", "400"))

CHAR_WIDTH = 7.2
LINE_HEIGHT = 19
RANK_GAP = 56
NODE_GAP = 26
PADDING = 24


class MermaidError(Exception):
    """The block could not be drawn; the message says why."""


class MermaidUnsupported(MermaidError):
    def __init__(self, kind: str):
        super().__init__(f"{kind} diagrams are not supported")
        self.kind = kind


@dataclass
class Node:
    label: str
    shape: str = "rect"
    style: dict = field(default_factory=dict)
    subgraph: int = -1
    rank: int = 0
    width: float = 0.0
    height: float = 0.0
    x: float = 0.0
    y: float = 0.0


@dataclass
class Edge:
    src: str
    dst: str
    label: str = ""
    dotted: bool = False
    thick: bool = False
    arrow: bool = True
    arrow_start: bool = False


_COLOR = re.compile(r"^(#[0-9a-fA-F]{3,8}|[a-zA-Z]{1,20})$")
_NUMBER = re.compile(r"^\d{1,3}(\.\d{1,2})?(px)?$")


def render_mermaid(source: str) -> str:
    """Renders one mermaid block to SVG markup, or raises with the reason."""
    lines = [
        line for line in source.split("\n")
        if line.strip() and not line.strip().startswith("%%")
    ]
    if not lines:
        raise MermaidError("the block is empty")
    head = lines[0].strip()
    kind = head.split()[0].casefold()
    if kind in ("graph", "flowchart"):
        return _flowchart(head, lines[1:])
    if kind == "sequencediagram":
        return _sequence(lines[1:])
    if kind == "pie":
        return _pie(head, lines[1:])
    raise MermaidUnsupported(kind)


# -- shared helpers ---------------------------------------------------------


def _clean_label(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return html.unescape(text).strip()


def _measure(label: str) -> tuple[float, float]:
    lines = label.split("\n") or [""]
    width = max((len(line) for line in lines), default=1) * CHAR_WIDTH + 24
    return max(width, 46.0), LINE_HEIGHT * len(lines) + 14


def _text(x: float, y: float, label: str, css: str = "mermaid-text", size: int = 12) -> str:
    lines = label.split("\n")
    top = y - (len(lines) - 1) * LINE_HEIGHT / 2
    spans = "".join(
        f'<tspan x="{x:.1f}" y="{top + index * LINE_HEIGHT:.1f}">{html.escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return (
        f'<text class="{css}" font-size="{size}" text-anchor="middle" '
        f'dominant-baseline="middle">{spans}</text>'
    )


def _style_attr(style: dict) -> str:
    """Author styling as an inline style attribute, colors and widths validated."""
    parts = []
    for key in ("stroke", "fill"):
        value = style.get(key, "")
        if value and _COLOR.match(value):
            parts.append(f"{key}:{value}")
    width = style.get("stroke-width", "")
    if width and _NUMBER.match(width):
        parts.append(f"stroke-width:{width.removesuffix('px')}")
    return f' style="{";".join(parts)}"' if parts else ""


# -- flowcharts -------------------------------------------------------------

_SHAPES = [
    (re.compile(r"^\(\[(?P<t>.*)\]\)$", re.S), "stadium"),
    (re.compile(r"^\[\((?P<t>.*)\)\]$", re.S), "cylinder"),
    (re.compile(r"^\(\((?P<t>.*)\)\)$", re.S), "circle"),
    (re.compile(r"^\[\[(?P<t>.*)\]\]$", re.S), "subroutine"),
    (re.compile(r"^\{\{(?P<t>.*)\}\}$", re.S), "hexagon"),
    (re.compile(r"^\[(?P<t>.*)\]$", re.S), "rect"),
    (re.compile(r"^\((?P<t>.*)\)$", re.S), "rounded"),
    (re.compile(r"^\{(?P<t>.*)\}$", re.S), "diamond"),
    (re.compile(r"^>(?P<t>.*)\]$", re.S), "flag"),
]

_NODE_REF = re.compile(
    r"""^\s*(?P<id>[\w.$/-]+)
    (?P<shape>\(\[.*?\]\)|\[\(.*?\)\]|\(\(.*?\)\)|\[\[.*?\]\]|\{\{.*?\}\}|
     \[[^\]]*\]|\([^)]*\)|\{[^}]*\}|>[^\]]*\])?
    (?::::(?P<cls>[\w-]+))?\s*""",
    re.X | re.S,
)

_EDGE_OP = re.compile(
    r"(<-\.+->|<-{2,}>|<={2,}>|-\.+->|-\.+-[xo]|-\.+-|={2,}>|={3,}(?=\s|$)|-{2,}[>xo]|-{3,})"
)
_INLINE_LABEL = re.compile(
    r"(?<![-<])(--|-\.|==)(?![-=.>])\s+([^-=<>|][^-=|]*?)\s+(-->|--[xo]|---|\.->|\.-|==>|===)"
)
_INLINE_DOTTED = re.compile(r"-\.\s*([^.|>][^.|]*?)\s*\.->")


def _mask_quotes(text: str) -> tuple[str, list[str]]:
    """Hides quoted spans so edge operators inside labels cannot split them."""
    stash: list[str] = []

    def hide(match):
        stash.append(match.group(1))
        return f"\x00{len(stash) - 1}\x00"

    return re.sub(r'"([^"]*)"', hide, text), stash


def _unmask(text: str, stash: list[str]) -> str:
    return re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)


def _join_statements(lines: list[str]) -> list[str]:
    """Joins lines while brackets or quotes are open, so labels may span lines."""
    statements: list[str] = []
    buffer = ""
    for line in lines:
        buffer = f"{buffer}\n{line}" if buffer else line
        depth = 0
        quoted = False
        for char in buffer:
            if char == '"':
                quoted = not quoted
            elif not quoted and char in "[({":
                depth += 1
            elif not quoted and char in "])}":
                depth -= 1
        if depth <= 0 and not quoted:
            statements.append(buffer)
            buffer = ""
    if buffer:
        statements.append(buffer)
    return statements


def _inline_to_pipe(statement: str) -> str:
    def swap(match):
        trail = match.group(3)
        op = {"-->": "-->", "---": "---", "--x": "--x", "--o": "--o",
              ".->": "-.->", ".-": "-.-", "==>": "==>", "===": "==="}[trail]
        return f" {op}|{match.group(2).strip()}| "

    return _INLINE_LABEL.sub(swap, statement)


def _parse_node_ref(
    chunk: str, nodes: dict, subgraph: int, stash: list[str], class_of: dict
) -> list[str]:
    ids = []
    for part in chunk.split("&"):
        part = part.strip()
        if not part:
            continue
        match = _NODE_REF.match(part)
        if not match or match.end() != len(part):
            raise MermaidError(f"could not read “{_unmask(part, stash)}”")
        node_id = match.group("id")
        shape_src = match.group("shape")
        if match.group("cls"):
            class_of[node_id] = match.group("cls")
        if node_id not in nodes:
            nodes[node_id] = Node(label=node_id, subgraph=subgraph)
        if shape_src:
            for pattern, shape in _SHAPES:
                shaped = pattern.match(shape_src)
                if shaped:
                    label = _clean_label(_unmask(shaped.group("t"), stash))
                    nodes[node_id].label = label or node_id
                    nodes[node_id].shape = shape
                    break
        if nodes[node_id].subgraph < 0 <= subgraph:
            nodes[node_id].subgraph = subgraph
        ids.append(node_id)
    return ids


def _parse_decls(decls: str) -> dict:
    style = {}
    for piece in decls.split(","):
        if ":" in piece:
            key, _, value = piece.partition(":")
            style[key.strip()] = value.strip()
    return style


def _parse_flowchart(header: str, lines: list[str]):
    direction = header.split()[1].upper() if len(header.split()) > 1 else "TD"
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    subgraphs: list[str] = []
    class_defs: dict[str, dict] = {}
    class_of: dict[str, str] = {}
    current = -1
    for raw in _join_statements(lines):
        line = raw.strip().rstrip(";")
        if not line:
            continue
        word = line.split()[0]
        if word == "subgraph":
            title = line[len("subgraph"):].strip()
            boxed = re.match(r"^[\w.-]+\s*\[(?P<t>.*)\]$", title)
            subgraphs.append(_clean_label(boxed.group("t") if boxed else title))
            current = len(subgraphs) - 1
            continue
        if line == "end":
            current = -1
            continue
        if word == "direction":
            continue
        if word in ("linkStyle", "click", "accTitle", "accDescr"):
            continue
        if word == "style":
            match = re.match(r"^style\s+(\S+)\s+(.*)$", line)
            if match and match.group(1) in nodes:
                nodes[match.group(1)].style.update(_parse_decls(match.group(2)))
            elif match:
                class_of.setdefault(match.group(1), "")
                nodes.setdefault(match.group(1), Node(label=match.group(1)))
                nodes[match.group(1)].style.update(_parse_decls(match.group(2)))
            continue
        if word == "classDef":
            match = re.match(r"^classDef\s+(\S+)\s+(.*)$", line)
            if match:
                class_defs[match.group(1)] = _parse_decls(match.group(2))
            continue
        if word == "class":
            match = re.match(r"^class\s+(\S+)\s+(\S+)$", line)
            if match:
                for node_id in match.group(1).split(","):
                    class_of[node_id.strip()] = match.group(2)
            continue
        masked, stash = _mask_quotes(line)
        statement = _inline_to_pipe(_INLINE_DOTTED.sub(r"-.->|\1|", masked))
        parts = _EDGE_OP.split(statement)
        sources = _parse_node_ref(parts[0], nodes, current, stash, class_of)
        index = 1
        while index < len(parts) - 1:
            op = parts[index]
            rest = parts[index + 1]
            label = ""
            label_match = re.match(r'^\s*\|([^|]*)\|\s*', rest)
            if label_match:
                label = _clean_label(_unmask(label_match.group(1), stash))
                rest = rest[label_match.end():]
            targets = _parse_node_ref(rest, nodes, current, stash, class_of)
            for src in sources:
                for dst in targets:
                    edges.append(Edge(
                        src, dst, label,
                        dotted="-." in op,
                        thick="=" in op,
                        arrow=op.endswith((">", "x", "o")),
                        arrow_start=op.startswith("<"),
                    ))
            sources = targets
            index += 2
    for node_id, name in class_of.items():
        if node_id in nodes and name in class_defs:
            merged = dict(class_defs[name])
            merged.update(nodes[node_id].style)
            nodes[node_id].style = merged
    if len(nodes) > MAX_DIAGRAM_NODES:
        raise MermaidError(f"diagram exceeds {MAX_DIAGRAM_NODES} nodes")
    return direction, nodes, edges, subgraphs


def _back_edges(nodes: dict, edges: list[Edge]) -> set[tuple[str, str]]:
    """Edges that close a cycle; ranking ignores them so ranks stay meaningful."""
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    for edge in edges:
        if edge.src in adjacency and edge.dst in adjacency:
            adjacency[edge.src].append(edge.dst)
    color = dict.fromkeys(nodes, 0)
    back: set[tuple[str, str]] = set()
    for start in nodes:
        if color[start]:
            continue
        color[start] = 1
        stack = [(start, iter(adjacency[start]))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                color[node] = 2
                stack.pop()
            elif color[child] == 0:
                color[child] = 1
                stack.append((child, iter(adjacency[child])))
            elif color[child] == 1:
                back.add((node, child))
    return back


def _layout(direction: str, nodes: dict, edges: list[Edge]) -> None:
    back = _back_edges(nodes, edges)
    rank = dict.fromkeys(nodes, 0)
    for _ in range(len(nodes)):
        changed = False
        for edge in edges:
            if (edge.src, edge.dst) in back:
                continue
            if edge.src in rank and edge.dst in rank and rank[edge.dst] < rank[edge.src] + 1:
                rank[edge.dst] = rank[edge.src] + 1
                changed = True
        if not changed:
            break
    order: dict[int, list[str]] = {}
    for node_id in nodes:
        order.setdefault(rank[node_id], []).append(node_id)
    ranks = [order[key] for key in sorted(order)]
    position = {n: i for row in ranks for i, n in enumerate(row)}
    incoming: dict[str, list[str]] = {}
    for edge in edges:
        incoming.setdefault(edge.dst, []).append(edge.src)
    for _ in range(3):
        for row in ranks:
            row.sort(key=lambda n: (
                nodes[n].subgraph,
                sum(position[p] for p in incoming.get(n, [])) / len(incoming.get(n, [1]))
                if incoming.get(n) else position[n],
            ))
            for i, n in enumerate(row):
                position[n] = i
    for node in nodes.values():
        node.width, node.height = _measure(node.label)
        if node.shape == "diamond":
            node.width += 22
            node.height += 14
        if node.shape == "circle":
            node.width = node.height = max(node.width * 0.8, node.height + 18)
    horizontal = direction in ("LR", "RL")
    # A labeled edge needs room in the gap it crosses, or the label sits on nodes.
    rank_index = {node_id: index for index, row in enumerate(ranks) for node_id in row}
    for node_id, node in nodes.items():
        node.rank = rank_index[node_id]
    gaps = [float(RANK_GAP)] * max(len(ranks) - 1, 1)
    for edge in edges:
        if not edge.label or edge.src not in rank_index or edge.dst not in rank_index:
            continue
        label_width, label_height = _measure(edge.label)
        need = (label_width if horizontal else label_height) + 14
        low = min(rank_index[edge.src], rank_index[edge.dst])
        high = max(rank_index[edge.src], rank_index[edge.dst])
        for gap in range(low, min(high, len(gaps))):
            gaps[gap] = max(gaps[gap], need)
    main = PADDING
    placed_rows = []
    for index, row in enumerate(ranks):
        thickness = max((n_.height if not horizontal else n_.width) for n_ in
                        (nodes[i] for i in row))
        span = sum((nodes[i].width if not horizontal else nodes[i].height) + NODE_GAP
                   for i in row) - NODE_GAP
        placed_rows.append((row, main + thickness / 2, span))
        main += thickness + (gaps[index] if index < len(gaps) else RANK_GAP)
    widest = max((span for _, _, span in placed_rows), default=0)
    for row, center, span in placed_rows:
        cross = PADDING + (widest - span) / 2
        for node_id in row:
            node = nodes[node_id]
            if horizontal:
                node.x, node.y = center, cross + node.height / 2
                cross += node.height + NODE_GAP
            else:
                node.x, node.y = cross + node.width / 2, center
                cross += node.width + NODE_GAP
    if direction in ("RL", "BT"):
        extent = max((n.x if direction == "RL" else n.y) for n in nodes.values()) + PADDING
        for node in nodes.values():
            if direction == "RL":
                node.x = extent - node.x
            else:
                node.y = extent - node.y


def _shape_svg(node: Node) -> str:
    x, y, w, h = node.x, node.y, node.width, node.height
    left, top = x - w / 2, y - h / 2
    style = _style_attr(node.style)
    if node.shape == "diamond":
        points = f"{x},{top} {x + w / 2},{y} {x},{top + h} {x - w / 2},{y}"
        return f'<polygon class="mermaid-node" points="{points}"{style} />'
    if node.shape == "hexagon":
        inset = h / 2
        points = (f"{left + inset},{top} {left + w - inset},{top} {left + w},{y} "
                  f"{left + w - inset},{top + h} {left + inset},{top + h} {left},{y}")
        return f'<polygon class="mermaid-node" points="{points}"{style} />'
    if node.shape == "circle":
        return (f'<ellipse class="mermaid-node" cx="{x}" cy="{y}" '
                f'rx="{w / 2}" ry="{h / 2}"{style} />')
    if node.shape == "flag":
        points = (f"{left},{top} {left + w},{top} {left + w},{top + h} "
                  f"{left},{top + h} {left + 12},{y}")
        return f'<polygon class="mermaid-node" points="{points}"{style} />'
    if node.shape == "cylinder":
        ry = 6
        body = (f'<path class="mermaid-node" d="M {left} {top + ry} '
                f'A {w / 2} {ry} 0 0 1 {left + w} {top + ry} '
                f'L {left + w} {top + h - ry} '
                f'A {w / 2} {ry} 0 0 1 {left} {top + h - ry} Z"{style} />')
        lid = (f'<ellipse class="mermaid-node" cx="{x}" cy="{top + ry}" '
               f'rx="{w / 2}" ry="{ry}"{style} />')
        return body + lid
    if node.shape == "subroutine":
        outer = (f'<rect class="mermaid-node" x="{left}" y="{top}" width="{w}" '
                 f'height="{h}" rx="3"{style} />')
        bars = (f'<line class="mermaid-edge" x1="{left + 6}" y1="{top}" '
                f'x2="{left + 6}" y2="{top + h}" />'
                f'<line class="mermaid-edge" x1="{left + w - 6}" y1="{top}" '
                f'x2="{left + w - 6}" y2="{top + h}" />')
        return outer + bars
    radius = h / 2 if node.shape == "stadium" else (10 if node.shape == "rounded" else 4)
    return (f'<rect class="mermaid-node" x="{left}" y="{top}" width="{w}" '
            f'height="{h}" rx="{radius}"{style} />')


def _edge_svg(
    edge: Edge,
    nodes: dict,
    horizontal: bool,
    bow: float,
    label_t: float = 0.5,
    stagger: float = 0.0,
) -> tuple[str, str]:
    """Returns (path markup, label markup); labels are layered above every path."""
    src, dst = nodes[edge.src], nodes[edge.dst]
    if horizontal:
        forward = dst.x >= src.x
        x1 = src.x + (src.width / 2 if forward else -src.width / 2)
        x2 = dst.x + (-dst.width / 2 - 4 if forward else dst.width / 2 + 4)
        y1, y2 = src.y + bow, dst.y + bow
        mid = (x1 + x2) / 2
        path = (f"M {x1:.1f} {y1:.1f} C {mid:.1f} {y1 + bow:.1f} "
                f"{mid:.1f} {y2 + bow:.1f} {x2:.1f} {y2:.1f}")
        lx, ly = x1 + (x2 - x1) * label_t, y1 + (y2 - y1) * label_t + bow + stagger
    else:
        forward = dst.y >= src.y
        y1 = src.y + (src.height / 2 if forward else -src.height / 2)
        y2 = dst.y + (-dst.height / 2 - 4 if forward else dst.height / 2 + 4)
        x1, x2 = src.x + bow, dst.x + bow
        mid = (y1 + y2) / 2
        path = (f"M {x1:.1f} {y1:.1f} C {x1 + bow:.1f} {mid:.1f} "
                f"{x2 + bow:.1f} {mid:.1f} {x2:.1f} {y2:.1f}")
        lx, ly = x1 + (x2 - x1) * label_t + bow + stagger, y1 + (y2 - y1) * label_t
    dash = ' stroke-dasharray="5 4"' if edge.dotted else ""
    width = ' stroke-width="2.4"' if edge.thick else ""
    marker = ' marker-end="url(#mermaid-arrow)"' if edge.arrow else ""
    if edge.arrow_start:
        marker += ' marker-start="url(#mermaid-arrow)"'
    path_markup = f'<path class="mermaid-edge" d="{path}"{dash}{width}{marker} />'
    label_markup = ""
    if edge.label:
        lw, lh = _measure(edge.label)
        label_markup = (
            f'<rect class="edge-label-bg" x="{lx - lw / 2 + 6:.1f}" y="{ly - lh / 2 + 3:.1f}" '
            f'width="{lw - 12:.1f}" height="{lh - 6:.1f}" rx="4" />'
        ) + _text(lx, ly, edge.label, "edge-label", 11)
    return path_markup, label_markup


def _flowchart(header: str, lines: list[str]) -> str:
    direction, nodes, edges, subgraphs = _parse_flowchart(header, lines)
    if not nodes:
        raise MermaidError("no nodes found")
    _layout(direction, nodes, edges)
    horizontal = direction in ("LR", "RL")
    boxes = []
    for index, title in enumerate(subgraphs):
        members = [n for n in nodes.values() if n.subgraph == index]
        if not members:
            continue
        left = min(n.x - n.width / 2 for n in members) - 12
        right = max(n.x + n.width / 2 for n in members) + 12
        top = min(n.y - n.height / 2 for n in members) - 26
        bottom = max(n.y + n.height / 2 for n in members) + 12
        boxes.append(
            f'<rect class="mermaid-subgraph" x="{left}" y="{top}" '
            f'width="{right - left}" height="{bottom - top}" rx="8" />'
            f'<text class="mermaid-subgraph-title" font-size="11" x="{left + 8}" '
            f'y="{top + 15}">{html.escape(title)}</text>'
        )
    rank_index = {}
    for node_id, node in nodes.items():
        rank_index[node_id] = node.rank
    pairs = {(edge.src, edge.dst) for edge in edges}
    paths = ""
    labels = ""
    label_slots: dict[int, int] = {}
    for edge in edges:
        if edge.src not in nodes or edge.dst not in nodes:
            continue
        # A reverse twin bows outward so the two directions stay distinct.
        bow = 14.0 if (edge.dst, edge.src) in pairs and edge.src > edge.dst else 0.0
        # A label on a rank-spanning edge sits in its first gap, not on a node,
        # and labels sharing a gap stagger instead of stacking.
        span = abs(rank_index.get(edge.src, 0) - rank_index.get(edge.dst, 0))
        label_t = 0.5 / span if span > 1 else 0.5
        stagger = 0.0
        if edge.label:
            gap = min(rank_index.get(edge.src, 0), rank_index.get(edge.dst, 0))
            slot = label_slots.get(gap, 0)
            label_slots[gap] = slot + 1
            stagger = slot * 24.0
        path_markup, label_markup = _edge_svg(edge, nodes, horizontal, bow, label_t, stagger)
        paths += path_markup
        labels += label_markup
    body = "".join(boxes) + paths
    for node in nodes.values():
        body += _shape_svg(node) + _text(node.x, node.y, node.label)
    body += labels
    width = max(n.x + n.width / 2 for n in nodes.values()) + PADDING
    height = max(n.y + n.height / 2 for n in nodes.values()) + PADDING
    return _svg(width, height, body)


def _svg(width: float, height: float, body: str) -> str:
    defs = (
        '<defs><marker id="mermaid-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path class="mermaid-arrow" d="M 0 0 L 10 5 L 0 10 z" /></marker></defs>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}" role="img">{defs}{body}</svg>'
    )


# -- sequence diagrams ------------------------------------------------------

_MESSAGE = re.compile(
    r"^(?P<src>[\w.-]+?)\s*(?P<op>-->>|->>|-->|->|--[xX)]|-[xX)])\s*"
    r"(?P<dst>[\w.-]+)\s*:\s*(?P<text>.*)$"
)


def _sequence(lines: list[str]) -> str:
    participants: list[str] = []
    labels: dict[str, str] = {}
    rows: list[tuple] = []

    def ensure(name: str) -> None:
        if name not in participants:
            participants.append(name)
            labels.setdefault(name, name)

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        word = line.split()[0]
        if word in ("participant", "actor"):
            rest = line[len(word):].strip()
            name, _, alias = rest.partition(" as ")
            ensure(name.strip())
            if alias.strip():
                labels[name.strip()] = alias.strip()
            continue
        if word.casefold() in ("activate", "deactivate", "autonumber"):
            continue
        if word == "Note":
            match = re.match(r"^Note\s+(over|left of|right of)\s+([\w,.\s-]+?):\s*(.*)$", line)
            if match:
                names = [n.strip() for n in match.group(2).split(",")]
                for name in names:
                    ensure(name)
                rows.append(("note", names, _clean_label(match.group(3))))
            continue
        if word.casefold() in ("loop", "alt", "opt", "par", "critical", "else", "and"):
            rows.append(("band", word, line[len(word):].strip()))
            continue
        if line == "end":
            rows.append(("band", "end", ""))
            continue
        match = _MESSAGE.match(line)
        if match:
            ensure(match.group("src"))
            ensure(match.group("dst"))
            rows.append(("message", match.group("src"), match.group("dst"),
                         _clean_label(match.group("text")), "--" in match.group("op")))
            continue
        raise MermaidError(f"could not read “{line}”")
    if not participants:
        raise MermaidError("no participants found")

    x_of: dict[str, float] = {}
    cursor = PADDING
    box_h = 30.0
    for name in participants:
        width, _ = _measure(labels[name])
        x_of[name] = cursor + width / 2
        cursor += width + 44
    total_width = cursor - 44 + PADDING
    y = PADDING + box_h + 26
    body = ""
    for row in rows:
        if row[0] == "message":
            _, src, dst, text, dashed = row
            x1, x2 = x_of[src], x_of[dst]
            dash = ' stroke-dasharray="5 4"' if dashed else ""
            if src == dst:
                path = (f"M {x1} {y} C {x1 + 46} {y - 4} {x1 + 46} {y + 16} "
                        f"{x1 + 4} {y + 14}")
                body += (f'<path class="mermaid-edge" d="{path}"{dash} '
                         'marker-end="url(#mermaid-arrow)" />')
                if text:
                    body += _text(x1 + 56 + len(text) * CHAR_WIDTH / 2, y + 5, text,
                                  "edge-label", 11)
                y += 34
            else:
                if text:
                    body += _text((x1 + x2) / 2, y - 9, text, "edge-label", 11)
                body += (f'<line class="mermaid-edge" x1="{x1}" y1="{y}" x2="{x2}" '
                         f'y2="{y}"{dash} marker-end="url(#mermaid-arrow)" />')
                y += 30
        elif row[0] == "note":
            _, names, text = row
            xs = [x_of[n] for n in names if n in x_of]
            width, height = _measure(text)
            center = sum(xs) / len(xs)
            body += (f'<rect class="mermaid-note" x="{center - width / 2}" '
                     f'y="{y - height / 2}" width="{width}" height="{height}" rx="4" />')
            body += _text(center, y, text, "edge-label", 11)
            y += height + 14
        else:
            _, word, text = row
            if word != "end":
                label = f"{word} {text}".strip()
                body += (f'<rect class="mermaid-band" x="{PADDING / 2}" y="{y - 11}" '
                         f'width="{total_width - PADDING}" height="22" rx="4" />')
                body += _text(total_width / 2, y, label, "edge-label", 11)
                y += 30
    bottom = y + 8
    heads = ""
    for name in participants:
        width, _ = _measure(labels[name])
        x = x_of[name]
        heads += (f'<line class="mermaid-lifeline" x1="{x}" y1="{PADDING + box_h}" '
                  f'x2="{x}" y2="{bottom}" />')
        heads += (f'<rect class="mermaid-node" x="{x - width / 2}" y="{PADDING}" '
                  f'width="{width}" height="{box_h}" rx="4" />')
        heads += _text(x, PADDING + box_h / 2, labels[name])
    return _svg(total_width, bottom + PADDING, heads + body)


# -- pie charts -------------------------------------------------------------

_PIE_PALETTE = ["#5b84c4", "#c4915b", "#7aa06a", "#b06a6a",
                "#8a7ab0", "#5ba3a3", "#b0a05b", "#8a8a8a"]


def _pie(header: str, lines: list[str]) -> str:
    title = ""
    match = re.search(r"\btitle\s+(.*)$", header)
    if match:
        title = _clean_label(match.group(1))
    slices: list[tuple[str, float]] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("title"):
            title = _clean_label(line[len("title"):])
            continue
        entry = re.match(r'^"(?P<label>[^"]*)"\s*:\s*(?P<value>[\d.]+)$', line)
        if not entry:
            raise MermaidError(f"could not read “{line}”")
        slices.append((entry.group("label"), float(entry.group("value"))))
    total = sum(value for _, value in slices)
    if not slices or total <= 0:
        raise MermaidError("no slices found")
    radius, cx = 84.0, PADDING + 84.0
    top = PADDING + (26 if title else 0)
    cy = top + radius
    body = ""
    if title:
        body += _text(cx, PADDING + 6, title, "mermaid-text", 13)
    angle = -math.pi / 2
    legend_x = cx + radius + 28
    for index, (label, value) in enumerate(slices):
        sweep = 2 * math.pi * value / total
        end = angle + sweep
        x1, y1 = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
        x2, y2 = cx + radius * math.cos(end), cy + radius * math.sin(end)
        large = 1 if sweep > math.pi else 0
        color = _PIE_PALETTE[index % len(_PIE_PALETTE)]
        if len(slices) == 1:
            body += (f'<circle class="mermaid-slice" cx="{cx}" cy="{cy}" r="{radius}" '
                     f'fill="{color}" />')
        else:
            body += (f'<path class="mermaid-slice" d="M {cx} {cy} L {x1:.1f} {y1:.1f} '
                     f'A {radius} {radius} 0 {large} 1 {x2:.1f} {y2:.1f} Z" '
                     f'fill="{color}" />')
        item_y = top + 10 + index * 22
        body += (f'<rect x="{legend_x}" y="{item_y - 7}" width="12" height="12" rx="2" '
                 f'fill="{color}" />')
        share = f"{label} — {value:g} ({value / total * 100:.0f}%)"
        body += (f'<text class="mermaid-text" font-size="12" x="{legend_x + 20}" '
                 f'y="{item_y + 3}">{html.escape(share)}</text>')
        angle = end
    longest = max(len(f"{label} — {value:g} (00%)") for label, value in slices)
    width = legend_x + 26 + longest * CHAR_WIDTH + PADDING
    height = max(cy + radius, top + 10 + len(slices) * 22) + PADDING
    return _svg(width, height, body)
