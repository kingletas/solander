"""Renders Obsidian `.base` files read-only: table views over the vault graph.

A base is YAML: filters, table views with column order and sort, and display
names. Filter strings share the Dataview evaluator (method calls desugar to
functions), with `==` normalized first. Plugin view types are named, not faked.
"""

import html
import os

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
    base_filter = data.get("filters")
    sections = []
    for view in views:
        name = str(view.get("name") or view.get("type") or "view")
        kind = str(view.get("type") or "")
        if kind != "table":
            sections.append(
                f'<div class="dataview-note">View “{html.escape(name)}” is a '
                f"{html.escape(kind)} plugin view — not rendered</div>"
            )
            continue
        try:
            sections.append(_table_view(engine, view, base_filter, display_names, name))
        except DqlError as error:
            sections.append(
                f'<div class="dataview-note">View “{html.escape(name)}” '
                f"not evaluated: {html.escape(str(error))}</div>"
            )
    return f'<div class="dataview">{"".join(sections)}</div>'


def _table_view(engine, view: dict, base_filter, display_names: dict, name: str) -> str:
    evaluator = Evaluator()
    rows = []
    for rel in sorted(engine.graph.props.keys()):
        row = engine._page_row(rel)
        if _passes(evaluator, base_filter, row) and _passes(evaluator, view.get("filters"), row):
            rows.append(row)
    for order in reversed(_sort_spec(view)):
        accessor = _accessor(str(order.get("property", "file.name")))
        rows.sort(
            key=lambda row, a=accessor: _sort_key(a(evaluator, row)),
            reverse=str(order.get("direction", "ASC")).upper() == "DESC",
        )
    truncated = len(rows) > MAX_BASE_ROWS
    rows = rows[:MAX_BASE_ROWS]
    columns = [str(column) for column in view.get("order") or ["file.name"]]
    headers = "".join(
        f"<th>{html.escape(display_names.get(column, _short(column)))}</th>"
        for column in columns
    )
    accessors = [_accessor(column) for column in columns]
    lines = []
    for row in rows:
        cells = []
        for column, accessor in zip(columns, accessors, strict=True):
            value = accessor(evaluator, row)
            if column == "file.name":
                file_ns = row.get("file")
                value = file_ns.get("link") if isinstance(file_ns, dict) else value
            cells.append(f"<td>{_value_html(value)}</td>")
        lines.append(f"<tr>{''.join(cells)}</tr>")
    notice = (
        f'<div class="dataview-note">Showing the first {MAX_BASE_ROWS} rows</div>'
        if truncated
        else ""
    )
    return (
        f"<h2>{html.escape(name)}</h2>"
        f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(lines)}</tbody></table>"
        f'<div class="dataview-note">{len(rows)} result(s)</div>{notice}'
    )


def _passes(evaluator: Evaluator, node, row: Row) -> bool:
    """Walks a filters tree: and/or/not combinators over expression strings."""
    if node is None:
        return True
    if isinstance(node, str):
        try:
            value = evaluator.evaluate(parse_expression(_normalize(node)), row)
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
