"""Evaluates Dataview queries in pure Python — no JavaScript, ever.

The engine executes the parsed DQL from `dql.py` against the vault graph's
metadata (frontmatter, file facts, links, tags, tasks) and renders app-authored,
escaped HTML. Anything outside the supported surface raises `DqlError`; the
renderer shows the reason with the original source, never a half-result.
"""

import datetime
import html
import re
from dataclasses import dataclass
from functools import cmp_to_key
from urllib.parse import quote

from .dql import (
    Binary,
    Call,
    DqlError,
    Field,
    Lambda,
    ListExpr,
    Literal,
    Query,
    SourceFolder,
    SourceLink,
    SourceNot,
    SourceOp,
    SourceTag,
    Unary,
    parse_expression,
    parse_query,
)

MAX_RESULT_ROWS = 2000

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?$")
_FILENAME_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")

_DUR_UNITS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
    "w": 604800, "wk": 604800, "week": 604800, "weeks": 604800,
    "mo": 2592000, "month": 2592000, "months": 2592000,
    "y": 31536000, "yr": 31536000, "year": 31536000, "years": 31536000,
}

# Luxon format tokens, longest first, mapped onto strftime pieces.
_LUXON = [
    ("yyyy", "%Y"), ("yy", "%y"), ("MMMM", "%B"), ("MMM", "%b"), ("MM", "%m"),
    ("dd", "%d"), ("cccc", "%A"), ("ccc", "%a"), ("HH", "%H"), ("hh", "%I"),
    ("mm", "%M"), ("ss", "%S"), ("a", "%p"), ("M", "%-m"), ("d", "%-d"),
]


@dataclass(frozen=True)
class Link:
    """A resolved link value: where it points and what it displays."""

    rel: str
    display: str


class Row:
    """One result row: name bindings over a page's fields, case-insensitive."""

    def __init__(self, props: dict, bindings: dict):
        self.props = props
        self.folded = {str(k).casefold(): v for k, v in props.items()}
        self.bindings = bindings

    def get(self, name: str):
        if name in self.bindings:
            return self.bindings[name]
        if name in self.props:
            return self.props[name]
        return self.folded.get(name.casefold())


class Evaluator:
    """Evaluates expression ASTs against a row and the query's `this` page."""

    def __init__(self, this_row: "Row | None" = None):
        self.this_row = this_row

    def evaluate(self, node, row: Row):
        if isinstance(node, Literal):
            return node.value
        if isinstance(node, ListExpr):
            return [self.evaluate(item, row) for item in node.items]
        if isinstance(node, Field):
            return self._field(node.parts, row)
        if isinstance(node, Unary):
            value = self.evaluate(node.operand, row)
            if node.operator == "!":
                return not _truthy(value)
            return -value if isinstance(value, (int, float)) else None
        if isinstance(node, Binary):
            return self._binary(node, row)
        if isinstance(node, Call):
            return self._call(node, row)
        if isinstance(node, Lambda):
            raise DqlError("a lambda is only valid as a function argument")
        raise DqlError(f"unsupported expression {type(node).__name__}")

    def _field(self, parts: tuple[str, ...], row: Row):
        head, *rest = parts
        if head == "this":
            if self.this_row is None:
                return None
            return self._field(tuple(rest), self.this_row) if rest else self.this_row
        value = row.get(head)
        for part in rest:
            value = _member(value, part)
        return value

    def _binary(self, node: Binary, row: Row):
        operator = node.operator
        if operator == "and":
            left = self.evaluate(node.left, row)
            return self.evaluate(node.right, row) if _truthy(left) else left
        if operator == "or":
            left = self.evaluate(node.left, row)
            return left if _truthy(left) else self.evaluate(node.right, row)
        left = self.evaluate(node.left, row)
        right = self.evaluate(node.right, row)
        if operator == ".":
            return _member(left, right)
        if operator == "index":
            if isinstance(left, list) and isinstance(right, (int, float)):
                position = int(right)
                return left[position] if -len(left) <= position < len(left) else None
            if isinstance(left, (Row, dict)):
                return _member(left, str(right))
            return None
        if operator == "=":
            return _equals(left, right)
        if operator == "!=":
            return not _equals(left, right)
        if operator in ("<", ">", "<=", ">="):
            ordering = _compare(left, right)
            if ordering is None:
                return False
            return {"<": ordering < 0, ">": ordering > 0,
                    "<=": ordering <= 0, ">=": ordering >= 0}[operator]
        if operator == "+":
            return _add(left, right)
        if operator == "-":
            return _subtract(left, right)
        if operator == "*":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left * right
            return None
        if operator == "/":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)) and right:
                return left / right
            return None
        if operator == "%":
            if isinstance(left, (int, float)) and isinstance(right, (int, float)) and right:
                return left % right
            return None
        raise DqlError(f"unsupported operator {operator!r}")

    def _call(self, node: Call, row: Row):
        name = node.name
        if name in ("choice", "if"):
            _arity(node, 3)
            condition = self.evaluate(node.arguments[0], row)
            branch = node.arguments[1] if _truthy(condition) else node.arguments[2]
            return self.evaluate(branch, row)
        if name in ("filter", "map"):
            _arity(node, 2)
            values = self.evaluate(node.arguments[0], row)
            function = node.arguments[1]
            if not isinstance(values, list) or not isinstance(function, Lambda):
                return None
            results = []
            for item in values:
                bound = Row(row.props, {**row.bindings, function.parameter: item})
                outcome = self.evaluate(function.body, bound)
                if name == "map":
                    results.append(outcome)
                elif _truthy(outcome):
                    results.append(item)
            return results
        arguments = [self.evaluate(argument, row) for argument in node.arguments]
        return _function(name, arguments)


def _arity(node: Call, count: int) -> None:
    if len(node.arguments) != count:
        raise DqlError(f"{node.name}() expects {count} arguments")


def _function(name: str, arguments: list):
    if name == "length":
        value = arguments[0] if arguments else None
        if value is None:
            return None
        if isinstance(value, (list, str, dict)):
            return len(value)
        return None
    if name == "date":
        return _to_date(arguments[0] if arguments else None)
    if name == "dur":
        amount, unit = arguments
        seconds = _DUR_UNITS.get(str(unit))
        if seconds is None:
            raise DqlError(f"unknown duration unit {unit!r}")
        return datetime.timedelta(seconds=amount * seconds)
    if name == "link":
        target = arguments[0]
        display = str(arguments[1]) if len(arguments) > 1 else None
        if isinstance(target, Link):
            return Link(target.rel, display or target.display)
        if isinstance(target, str):
            return Link(target, display or target)
        return None
    if name == "string":
        return _to_text(arguments[0]) if arguments else ""
    if name == "lower":
        return str(arguments[0]).casefold() if arguments[0] is not None else None
    if name == "upper":
        return str(arguments[0]).upper() if arguments[0] is not None else None
    if name == "dateformat":
        moment = _to_date(arguments[0])
        if moment is None:
            return None
        return _luxon_format(moment, str(arguments[1]))
    if name == "default":
        return arguments[0] if arguments[0] is not None else arguments[1]
    if name == "round":
        if arguments[0] is None:
            return None
        digits = int(arguments[1]) if len(arguments) > 1 else 0
        value = round(float(arguments[0]), digits)
        return int(value) if digits == 0 else value
    if name == "striptime":
        moment = _to_date(arguments[0])
        if isinstance(moment, datetime.datetime):
            return moment.date()
        return moment
    if name == "contains":
        haystack, needle = arguments[0], arguments[1]
        if haystack is None:
            return False
        if isinstance(haystack, str):
            return str(needle).casefold() in haystack.casefold()
        if isinstance(haystack, list):
            return any(_equals(item, needle) for item in haystack)
        return False
    if name == "econtains":
        haystack, needle = arguments[0], arguments[1]
        return isinstance(haystack, list) and any(_equals(i, needle) for i in haystack)
    if name == "sum":
        values = [v for v in (arguments[0] or []) if isinstance(v, (int, float))]
        return sum(values)
    if name in ("min", "max"):
        values = [v for v in (arguments[0] or []) if v is not None]
        if not values:
            return None
        return min(values) if name == "min" else max(values)
    if name == "startswith":
        return str(arguments[0] or "").casefold().startswith(str(arguments[1]).casefold())
    if name == "endswith":
        return str(arguments[0] or "").casefold().endswith(str(arguments[1]).casefold())
    if name == "join":
        separator = str(arguments[1]) if len(arguments) > 1 else ", "
        return separator.join(_to_text(v) for v in (arguments[0] or []))
    if name == "replace":
        if arguments[0] is None:
            return None
        return str(arguments[0]).replace(str(arguments[1]), str(arguments[2]))
    if name == "split":
        if arguments[0] is None:
            return None
        return str(arguments[0]).split(str(arguments[1]))
    if name in ("number", "tonumber"):
        try:
            return float(arguments[0])
        except (TypeError, ValueError):
            return None
    if name == "today":
        return datetime.date.today()
    if name == "now":
        return datetime.datetime.now()
    if name == "isempty":
        value = arguments[0]
        if value is None:
            return True
        if isinstance(value, (list, str, dict)):
            return len(value) == 0
        return False
    if name == "format":
        moment = _to_date(arguments[0])
        if moment is None:
            return None
        return _luxon_format(moment, str(arguments[1]))
    if name == "hastag":
        namespace, wanted = arguments[0], str(arguments[1]).lstrip("#").casefold()
        tags = namespace.get("tags", []) if isinstance(namespace, dict) else []
        return any(str(tag).lstrip("#").casefold() == wanted for tag in tags)
    if name == "infolder":
        namespace, wanted = arguments[0], str(arguments[1]).rstrip("/")
        folder = namespace.get("folder", "") if isinstance(namespace, dict) else ""
        return folder == wanted or folder.startswith(f"{wanted}/")
    if name == "hasproperty":
        namespace, wanted = arguments[0], str(arguments[1]).casefold()
        properties = namespace.get("properties") if isinstance(namespace, dict) else None
        if not isinstance(properties, dict):
            return False
        return any(str(key).casefold() == wanted for key in properties)
    if name == "typeof":
        value = arguments[0]
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, (datetime.date, datetime.datetime)):
            return "date"
        if isinstance(value, datetime.timedelta):
            return "duration"
        if isinstance(value, list):
            return "array"
        if isinstance(value, Link):
            return "link"
        return "string"
    raise DqlError(f"unsupported function {name}()")


def _member(value, part: str):
    if isinstance(value, Row):
        return value.get(part)
    if isinstance(value, dict):
        return value.get(part)
    if isinstance(value, Link) and part in ("path", "display"):
        return value.rel if part == "path" else value.display
    if isinstance(value, (datetime.date, datetime.datetime)):
        return {
            "year": value.year, "month": value.month, "day": value.day,
            "weekday": value.isoweekday(),
        }.get(part)
    if isinstance(value, list):
        collected = [_member(item, part) for item in value]
        return [item for item in collected if item is not None]
    return None


def _truthy(value) -> bool:
    if isinstance(value, Row):
        return True
    return bool(value)


def _to_date(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text == "today":
            return datetime.date.today()
        if text == "now":
            return datetime.datetime.now()
        if _ISO_DATE.match(text):
            try:
                if len(text) > 10:
                    return datetime.datetime.fromisoformat(text.replace(" ", "T"))
                return datetime.date.fromisoformat(text)
            except ValueError:
                return None
    return None


def _coerce_pair(left, right):
    """Lets an ISO string stand in for a date when the other side is one."""
    if isinstance(left, (datetime.date, datetime.datetime)) and isinstance(right, str):
        right = _to_date(right) or right
    elif isinstance(right, (datetime.date, datetime.datetime)) and isinstance(left, str):
        left = _to_date(left) or left
    if isinstance(left, datetime.datetime) and type(right) is datetime.date:
        right = datetime.datetime.combine(right, datetime.time())
    elif isinstance(right, datetime.datetime) and type(left) is datetime.date:
        left = datetime.datetime.combine(left, datetime.time())
    return left, right


def _equals(left, right) -> bool:
    left, right = _coerce_pair(left, right)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    return left == right


def _compare(left, right):
    left, right = _coerce_pair(left, right)
    if left is None or right is None:
        return None
    try:
        if left < right:
            return -1
        if left > right:
            return 1
        return 0
    except TypeError:
        return None


def _add(left, right):
    if isinstance(left, str) or isinstance(right, str):
        return _to_text(left) + _to_text(right)
    if isinstance(left, (datetime.date, datetime.datetime)) and isinstance(
        right, datetime.timedelta
    ):
        return left + right
    if isinstance(left, datetime.timedelta) and isinstance(right, datetime.timedelta):
        return left + right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left + right
    if isinstance(left, list) and isinstance(right, list):
        return left + right
    return None


def _subtract(left, right):
    left, right = _coerce_pair(left, right)
    if isinstance(left, (datetime.date, datetime.datetime)):
        if isinstance(right, datetime.timedelta):
            return left - right
        if isinstance(right, (datetime.date, datetime.datetime)):
            return left - right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left - right
    if isinstance(left, datetime.timedelta) and isinstance(right, datetime.timedelta):
        return left - right
    return None


def _luxon_format(moment, pattern: str) -> str:
    output = []
    position = 0
    while position < len(pattern):
        for token, strf in _LUXON:
            if pattern.startswith(token, position):
                piece = moment.strftime(strf.replace("%-", "%"))
                if strf.startswith("%-"):
                    piece = piece.lstrip("0") or "0"
                output.append(piece)
                position += len(token)
                break
        else:
            output.append(pattern[position])
            position += 1
    return "".join(output)


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, Link):
        return value.display
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return _duration_text(value)
    if isinstance(value, list):
        return ", ".join(_to_text(item) for item in value)
    return str(value)


def _duration_text(delta: datetime.timedelta) -> str:
    seconds = int(delta.total_seconds())
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _seconds = divmod(seconds, 60)
    pieces = []
    if days:
        pieces.append(f"{days} days")
    if hours:
        pieces.append(f"{hours} hours")
    if minutes:
        pieces.append(f"{minutes} minutes")
    return ", ".join(pieces) or "0 minutes"


# -- execution over the vault graph -----------------------------------------


def _note_uri(rel: str) -> str:
    return f"reader:///note/{quote(rel)}"


def _file_namespace(rel: str, graph) -> dict:
    filename = rel.rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0]
    folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
    mtime, size = (graph.meta or {}).get(rel, (None, None))
    moment = datetime.datetime.fromtimestamp(mtime) if mtime else None
    props = graph.props.get(rel, {}) or {}
    day_match = _FILENAME_DATE.search(stem)
    day = _to_date(day_match.group(1)) if day_match else None
    tags = sorted(graph.note_tags.get(rel, set()))
    outgoing = graph.outgoing.get(rel, [])
    return {
        "name": stem,
        "fullname": filename,
        "path": rel,
        "properties": props,
        "folder": folder,
        "ext": filename.rsplit(".", 1)[-1] if "." in filename else "",
        "link": Link(rel, stem),
        "size": size,
        "mtime": moment,
        "ctime": moment,
        "cday": moment.date() if moment else None,
        "day": day,
        "tags": [f"#{tag}" for tag in tags],
        "etags": [f"#{tag}" for tag in tags],
        "outlinks": [Link(o.path, o.target) for o in outgoing if o.kind == "note" and o.path],
        "inlinks": sorted(
            {Link(m.source, m.source.rsplit("/", 1)[-1].rsplit(".", 1)[0])
             for m in graph.backlinks.get(rel, [])},
            key=lambda link: link.rel,
        ),
    }


class DataviewEngine:
    """Runs DQL queries and inline expressions against one vault graph snapshot."""

    def __init__(self, graph):
        self.graph = graph

    def _page_row(self, rel: str) -> Row:
        props = self.graph.props.get(rel, {}) or {}
        return Row(props, {"file": _file_namespace(rel, self.graph)})

    def _pages(self, source, this_rel: str = "") -> list[str]:
        everything = sorted(self.graph.props.keys())
        if source is None:
            return everything
        return sorted(self._source_set(source, set(everything), this_rel))

    def _source_set(self, source, everything: set, this_rel: str = "") -> set:
        if isinstance(source, SourceLink):
            mentions = self.graph.backlinks.get(this_rel, [])
            return {mention.source for mention in mentions} & everything
        if isinstance(source, SourceFolder):
            prefix = source.path.rstrip("/")
            if not prefix:
                return set(everything)
            return {r for r in everything if r == prefix or r.startswith(f"{prefix}/")}
        if isinstance(source, SourceTag):
            return set(self.graph.notes_tagged(source.tag)) & everything
        if isinstance(source, SourceNot):
            return everything - self._source_set(source.operand, everything, this_rel)
        if isinstance(source, SourceOp):
            left = self._source_set(source.left, everything, this_rel)
            right = self._source_set(source.right, everything, this_rel)
            return left & right if source.operator == "and" else left | right
        raise DqlError("unsupported FROM source")

    def run_inline(self, text: str, this_rel: str) -> str:
        """Evaluates one inline expression in the context of the current note."""
        node = parse_expression(text)
        this_row = self._page_row(this_rel)
        value = Evaluator(this_row).evaluate(node, this_row)
        return _value_html(value)

    def run_query(self, text: str, this_rel: str) -> str:
        """Executes a DQL block and returns the escaped result markup."""
        query = parse_query(text)
        this_row = self._page_row(this_rel)
        evaluator = Evaluator(this_row)
        if query.kind == "task":
            rows = self._task_rows(query.source, this_rel)
        else:
            rows = [self._page_row(rel) for rel in self._pages(query.source, this_rel)]
        rows = self._apply_steps(rows, query.steps, evaluator)
        truncated = len(rows) > MAX_RESULT_ROWS
        rows = rows[:MAX_RESULT_ROWS]
        if query.kind == "table":
            body = _render_table(query, rows, evaluator)
        elif query.kind == "list":
            body = _render_list(query, rows, evaluator)
        else:
            body = _render_tasks(rows)
        notice = (
            f'<div class="dataview-note">Showing the first {MAX_RESULT_ROWS} rows</div>'
            if truncated
            else ""
        )
        return f'<div class="dataview">{body}{notice}</div>'

    def _task_rows(self, source, this_rel: str = "") -> list[Row]:
        rows = []
        for rel in self._pages(source, this_rel):
            file_ns = _file_namespace(rel, self.graph)
            props = self.graph.props.get(rel, {}) or {}
            for status, text in self.graph.tasks.get(rel, []):
                rows.append(
                    Row(
                        props,
                        {
                            "file": file_ns,
                            "text": text,
                            "status": status,
                            "completed": status.casefold() == "x",
                            "checked": status != " ",
                        },
                    )
                )
        return rows

    def _apply_steps(self, rows: list[Row], steps, evaluator: Evaluator) -> list[Row]:
        for step in steps:
            command = step[0]
            if command == "where":
                rows = [row for row in rows if _truthy(evaluator.evaluate(step[1], row))]
            elif command == "limit":
                rows = rows[: step[1]]
            elif command == "sort":
                rows = _sorted_rows(rows, step[1], evaluator)
            elif command == "flatten":
                flattened = []
                for row in rows:
                    value = evaluator.evaluate(step[1], row)
                    items = value if isinstance(value, list) else [value]
                    for item in items:
                        flattened.append(Row(row.props, {**row.bindings, step[2]: item}))
                rows = flattened
            elif command == "group":
                groups: dict = {}
                order: list = []
                for row in rows:
                    key = evaluator.evaluate(step[1], row)
                    marker = _to_text(key)
                    if marker not in groups:
                        groups[marker] = (key, [])
                        order.append(marker)
                    groups[marker][1].append(row)
                rows = [
                    Row({}, {step[2]: groups[m][0], "key": groups[m][0], "rows": groups[m][1]})
                    for m in order
                ]
        return rows


def _sorted_rows(rows: list[Row], keys, evaluator: Evaluator) -> list[Row]:
    evaluated = [(row, [evaluator.evaluate(key.expression, row) for key in keys]) for row in rows]

    def compare(a, b) -> int:
        for index, key in enumerate(keys):
            left, right = a[1][index], b[1][index]
            if left is None and right is None:
                continue
            if left is None:
                return 1
            if right is None:
                return -1
            ordering = _compare(left, right)
            if ordering is None:
                ordering = _compare(_to_text(left), _to_text(right)) or 0
            if ordering:
                return -ordering if key.descending else ordering
        return 0

    return [row for row, _ in sorted(evaluated, key=cmp_to_key(compare))]


def _value_html(value) -> str:
    if isinstance(value, Link):
        href = html.escape(_note_uri(value.rel), quote=True)
        return f'<a class="wikilink" href="{href}">{html.escape(value.display)}</a>'
    if isinstance(value, list):
        return ", ".join(_value_html(item) for item in value)
    if isinstance(value, Row):
        file_ns = value.get("file")
        if isinstance(file_ns, dict) and isinstance(file_ns.get("link"), Link):
            return _value_html(file_ns["link"])
        return _value_html(value.get("key"))
    if value is None:
        return "-"
    return html.escape(_to_text(value))


def _row_identity(row: Row) -> str:
    file_ns = row.get("file")
    if isinstance(file_ns, dict) and isinstance(file_ns.get("link"), Link):
        return _value_html(file_ns["link"])
    return _value_html(row.get("key"))


def _render_table(query: Query, rows: list[Row], evaluator: Evaluator) -> str:
    headers = [column.header for column in query.columns]
    if not query.without_id:
        headers = ["File" if rows and rows[0].get("file") else "Group", *headers]
    head = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    lines = []
    for row in rows:
        cells = []
        if not query.without_id:
            cells.append(f"<td>{_row_identity(row)}</td>")
        for column in query.columns:
            cells.append(f"<td>{_value_html(evaluator.evaluate(column.expression, row))}</td>")
        lines.append(f"<tr>{''.join(cells)}</tr>")
    count = f'<div class="dataview-note">{len(rows)} result(s)</div>' if not rows else ""
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(lines)}</tbody></table>{count}"


def _render_list(query: Query, rows: list[Row], evaluator: Evaluator) -> str:
    items = []
    for row in rows:
        if query.columns:
            value = _value_html(evaluator.evaluate(query.columns[0].expression, row))
            items.append(f"<li>{_row_identity(row)}: {value}</li>")
        else:
            items.append(f"<li>{_row_identity(row)}</li>")
    if not items:
        return '<div class="dataview-note">0 result(s)</div>'
    return f"<ul>{''.join(items)}</ul>"


def _render_tasks(rows: list[Row]) -> str:
    items = []
    for row in rows:
        checked = " checked" if row.get("checked") else ""
        source = ""
        file_ns = row.get("file")
        if isinstance(file_ns, dict) and isinstance(file_ns.get("link"), Link):
            source = f' <span class="dataview-source">{_value_html(file_ns["link"])}</span>'
        items.append(
            f'<li class="task-list-item"><input type="checkbox" disabled{checked} /> '
            f"{html.escape(str(row.get('text') or ''))}{source}</li>"
        )
    if not items:
        return '<div class="dataview-note">0 task(s)</div>'
    return f'<ul class="contains-task-list">{"".join(items)}</ul>'
