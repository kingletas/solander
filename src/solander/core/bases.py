"""Renders Obsidian `.base` files read-only: table views over the vault graph.

A base is YAML: filters, formulas, table views with column order, sort, groups
and a row limit, and display names. Filter strings share the Dataview evaluator
(method calls desugar to functions), with `==` normalized first. Plugin view
types are named, not faked.
"""

import html
import os
from functools import lru_cache

import yaml

from .dataview import DataviewEngine, Evaluator, Row, _to_text, _value_html
from .dql import DqlError, parse_expression

MAX_BASE_BYTES = int(os.environ.get("READER_MAX_BASE_BYTES", str(1024 * 1024)))
MAX_BASE_ROWS = 500


def render_base(graph, text: str) -> str:
    """Renders every view of a base file into escaped markup."""
    if len(text.encode("utf-8", errors="replace")) > MAX_BASE_BYTES:
        return _message("This base file is too large to render")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        return _message(f"This base file is not valid YAML: {error}")
    if not isinstance(data, dict):
        return _message("This base file has no views")
    views = [view for view in data.get("views") or [] if isinstance(view, dict)]
    if not views:
        return _message("This base file has no views")
    engine = DataviewEngine(graph)
    display_names = _display_names(data.get("properties"))
    try:
        formulas = _parse_formulas(data.get("formulas"))
    except DqlError as error:
        return _message(f"This base file has a formula that cannot be read: {error}")
    evaluator = Evaluator(graph=graph)
    base_rows, base_error = [], None
    if any(str(view.get("type") or "") == "table" for view in views):
        try:
            base_rows = _base_rows(engine, evaluator, data.get("filters"), formulas)
        except DqlError as error:
            base_error = error
    sections = []
    for view in views:
        name = str(view.get("name") or view.get("type") or "view")
        kind = str(view.get("type") or "")
        if kind != "table":
            sections.append(
                f'<div class="dataview-note">View “{html.escape(name)}” is a '
                f"{html.escape(kind)} plugin view, which is not rendered</div>"
            )
            continue
        try:
            if base_error is not None:
                raise base_error
            sections.append(_table_view(evaluator, view, base_rows, display_names, name))
        except DqlError as error:
            sections.append(
                f'<div class="dataview-note">View “{html.escape(name)}” '
                f"not evaluated: {html.escape(str(error))}</div>"
            )
    return f'<div class="dataview">{"".join(sections)}</div>'


def _base_rows(engine, evaluator: Evaluator, base_filter, formulas: dict) -> list:
    """Every note the base's own filter admits, each carrying its formulas.

    Views share these rows, so a formula one view reads is not worked out again
    for the next.
    """
    rows = []
    for rel in sorted(engine.graph.props.keys()):
        row = engine._page_row(rel)
        row.bindings["formula"] = _Formulas(evaluator, formulas, row)
        if _passes(evaluator, base_filter, row):
            rows.append(row)
    return rows


def _table_view(
    evaluator: Evaluator, view: dict, base_rows: list, display_names: dict, name: str
) -> str:
    view_filter = view.get("filters")
    rows = [row for row in base_rows if _passes(evaluator, view_filter, row)]
    for order in reversed(_sort_spec(view)):
        accessor = _accessor(str(order.get("property", "file.name")))
        rows.sort(
            key=lambda row, a=accessor: _sort_key(a(evaluator, row)),
            reverse=str(order.get("direction", "ASC")).upper() == "DESC",
        )
    cap = min(_limit(view) or MAX_BASE_ROWS, MAX_BASE_ROWS)
    truncated = len(rows) > cap
    rows = rows[:cap]
    columns = [str(column) for column in view.get("order") or ["file.name"]]
    headers = "".join(
        f"<th>{html.escape(display_names.get(column, _short(column)))}</th>"
        for column in columns
    )
    accessors = [_accessor(column) for column in columns]
    lines = []
    for label, members in _groups(evaluator, view, rows):
        if label is not None:
            lines.append(
                f'<tr class="base-group"><th colspan="{len(columns)}">'
                f"{html.escape(label)} ({len(members)})</th></tr>"
            )
        for row in members:
            cells = []
            for column, accessor in zip(columns, accessors, strict=True):
                value = accessor(evaluator, row)
                if column == "file.name":
                    file_ns = row.get("file")
                    value = file_ns.get("link") if isinstance(file_ns, dict) else value
                cells.append(f"<td>{_value_html(value)}</td>")
            lines.append(f"<tr>{''.join(cells)}</tr>")
    notice = (
        f'<div class="dataview-note">Showing the first {cap} rows</div>'
        if truncated
        else ""
    )
    return (
        f"<h2>{html.escape(name)}</h2>"
        f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(lines)}</tbody></table>"
        f'<div class="dataview-note">{len(rows)} result(s)</div>{notice}'
    )


class _Formulas(dict):
    """A row's `formula.NAME` values, each evaluated the first time it is read.

    One formula may name another; one that reaches itself is an error, not a loop.
    """

    def __init__(self, evaluator: Evaluator, expressions: dict, row: Row):
        super().__init__()
        self._evaluator = evaluator
        self._expressions = expressions
        self._row = row
        self._reading: set = set()

    def get(self, name, default=None):
        if name in self:
            return self[name]
        expression = self._expressions.get(name)
        if expression is None:
            return default
        if name in self._reading:
            raise DqlError(f"formula {name!r} refers to itself")
        self._reading.add(name)
        try:
            value = self._evaluator.evaluate(expression, self._row)
        finally:
            self._reading.discard(name)
        self[name] = value
        return value


def _parse_formulas(formulas) -> dict:
    parsed = {}
    if isinstance(formulas, dict):
        for name, text in formulas.items():
            try:
                parsed[str(name)] = parse_expression(_normalize(str(text)))
            except DqlError as error:
                raise DqlError(f"{name}: {error}") from error
    return parsed


def _limit(view: dict) -> int:
    limit = view.get("limit")
    return limit if isinstance(limit, int) and not isinstance(limit, bool) and limit > 0 else 0


def _groups(evaluator: Evaluator, view: dict, rows: list) -> list:
    """Splits sorted rows by the view's `groupBy` value, keeping their order inside each group.

    Without a `groupBy`, the rows are one unlabelled group.
    """
    spec = view.get("groupBy")
    if not isinstance(spec, dict) or not spec.get("property"):
        return [(None, rows)]
    accessor = _accessor(str(spec["property"]))
    groups: dict = {}
    for row in rows:
        value = accessor(evaluator, row)
        label = _to_text(value) if value not in (None, "", []) else "No value"
        groups.setdefault(label, []).append(row)
    descending = str(spec.get("direction", "ASC")).upper() == "DESC"
    labels = sorted(groups, key=lambda label: label.casefold(), reverse=descending)
    return [(label, groups[label]) for label in labels]


def _passes(evaluator: Evaluator, node, row: Row) -> bool:
    """Walks a filters tree: and/or/not combinators over expression strings."""
    if node is None:
        return True
    if isinstance(node, str):
        try:
            value = evaluator.evaluate(_parsed(node), row)
        except DqlError as error:
            raise DqlError(f"filter {node!r}: {error}") from error
        return bool(value)
    if isinstance(node, dict):
        for key, children in node.items():
            items = children if isinstance(children, list) else [children]
            if key == "and":
                if not all(_passes(evaluator, child, row) for child in items):
                    return False
            elif key == "or":
                if not any(_passes(evaluator, child, row) for child in items):
                    return False
            elif key == "not":
                if any(_passes(evaluator, child, row) for child in items):
                    return False
            else:
                raise DqlError(f"unsupported filter combinator {key!r}")
        return True
    raise DqlError("unsupported filter shape")


@lru_cache(maxsize=1024)
def _parsed(expression: str):
    """One filter string's syntax tree, parsed once however many rows ask for it."""
    return parse_expression(_normalize(expression))


def _normalize(expression: str) -> str:
    """Bases writes `==` where the evaluator's grammar uses `=`."""
    return expression.replace("==", "=").replace("! =", "!=")


def _accessor(column: str):
    """A column reader: a parsed expression, or a plain (possibly spaced) field name."""
    try:
        expression = parse_expression(_normalize(column))
    except DqlError:
        name = _short(column)
        return lambda _evaluator, row: row.get(name)
    return lambda evaluator, row: evaluator.evaluate(expression, row)


def _sort_spec(view: dict) -> list[dict]:
    spec = view.get("sort")
    return [entry for entry in spec if isinstance(entry, dict)] if isinstance(spec, list) else []


def _display_names(properties) -> dict:
    names = {}
    if isinstance(properties, dict):
        for key, config in properties.items():
            if isinstance(config, dict) and config.get("displayName"):
                names[str(key).removeprefix("note.")] = str(config["displayName"])
                names[str(key)] = str(config["displayName"])
    return names


def _short(column: str) -> str:
    return column.removeprefix("note.")


def _sort_key(value):
    return (value is None, _to_text(value).casefold())


def _message(text: str) -> str:
    return f'<div class="message-state"><h1>Cannot render base</h1><p>{html.escape(text)}</p></div>'
