"""Parses Dataview's query language: expressions, sources, and query commands.

This is a parser only — evaluation lives in `dataview.py`. Anything outside the
implemented grammar raises `DqlError` with a reason the renderer shows verbatim.
"""

import re
from dataclasses import dataclass, field


class DqlError(Exception):
    """A query or expression the engine does not accept, with the reason."""


# -- expression AST ---------------------------------------------------------


@dataclass(frozen=True)
class Literal:
    value: object


@dataclass(frozen=True)
class Field:
    """A dotted identifier: `mood`, `file.name`, `this.start`."""

    parts: tuple[str, ...]


@dataclass(frozen=True)
class ListExpr:
    items: tuple


@dataclass(frozen=True)
class Unary:
    operator: str
    operand: object


@dataclass(frozen=True)
class Binary:
    operator: str
    left: object
    right: object


@dataclass(frozen=True)
class Call:
    name: str
    arguments: tuple


@dataclass(frozen=True)
class Lambda:
    parameter: str
    body: object


# -- query AST --------------------------------------------------------------


@dataclass(frozen=True)
class Column:
    expression: object
    header: str


@dataclass(frozen=True)
class SortKey:
    expression: object
    descending: bool = False


@dataclass(frozen=True)
class SourceFolder:
    path: str


@dataclass(frozen=True)
class SourceTag:
    tag: str


@dataclass(frozen=True)
class SourceLink:
    """`FROM [[]]` — the pages that link to the query's own note."""

    target: str = ""


@dataclass(frozen=True)
class SourceOp:
    operator: str
    left: object
    right: object


@dataclass(frozen=True)
class SourceNot:
    operand: object


@dataclass(frozen=True)
class Query:
    kind: str
    columns: tuple[Column, ...] = ()
    without_id: bool = False
    source: object = None
    steps: tuple = field(default_factory=tuple)


_TOKEN = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<number>\d+(\.\d+)?)
  | (?P<string>"(?:[^"\\]|\\.)*")
  | (?P<tag>\#[\w/-]+)
  | (?P<name>[A-Za-z_][\w-]*)
  | (?P<op><=|>=|!=|=>|[-+*/%()\[\],.!<>=&|])
    """,
    re.VERBOSE,
)

_KEYWORDS = {
    "and", "or", "true", "false", "null", "asc", "desc", "as", "from", "where",
    "sort", "limit", "flatten", "group", "by", "without", "id",
}


@dataclass(frozen=True)
class Token:
    kind: str
    text: str


def _lex(text: str) -> list[Token]:
    tokens: list[Token] = []
    position = 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None:
            raise DqlError(f"unexpected character {text[position]!r}")
        position = match.end()
        kind = match.lastgroup
        if kind == "ws":
            continue
        value = match.group(0)
        if kind == "name" and value.casefold() in _KEYWORDS:
            tokens.append(Token(value.casefold(), value))
        else:
            tokens.append(Token(kind, value))
    tokens.append(Token("end", ""))
    return tokens


class _Parser:
    """A Pratt parser over the token stream; shared by expressions and queries."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.position = 0

    def peek(self) -> Token:
        return self.tokens[self.position]

    def advance(self) -> Token:
        token = self.tokens[self.position]
        self.position += 1
        return token

    def expect(self, kind: str) -> Token:
        token = self.advance()
        if token.kind != kind:
            raise DqlError(f"expected {kind}, found {token.text or 'end of input'!r}")
        return token

    def at_end(self) -> bool:
        return self.peek().kind == "end"

    # -- expressions (precedence climbing) ---------------------------------

    def expression(self) -> object:
        return self._or()

    def _or(self):
        node = self._and()
        while self.peek().kind == "or" or self.peek().text == "|":
            self.advance()
            node = Binary("or", node, self._and())
        return node

    def _and(self):
        node = self._comparison()
        while self.peek().kind == "and" or self.peek().text == "&":
            self.advance()
            node = Binary("and", node, self._comparison())
        return node

    def _comparison(self):
        node = self._additive()
        while self.peek().text in ("=", "!=", "<", ">", "<=", ">="):
            operator = self.advance().text
            node = Binary(operator, node, self._additive())
        return node

    def _additive(self):
        node = self._multiplicative()
        while self.peek().text in ("+", "-"):
            operator = self.advance().text
            node = Binary(operator, node, self._multiplicative())
        return node

    def _multiplicative(self):
        node = self._unary()
        while self.peek().text in ("*", "/", "%"):
            operator = self.advance().text
            node = Binary(operator, node, self._unary())
        return node

    def _unary(self):
        token = self.peek()
        if token.text == "!":
            self.advance()
            return Unary("!", self._unary())
        if token.text == "-":
            self.advance()
            return Unary("-", self._unary())
        return self._postfix()

    def _postfix(self):
        node = self._primary()
        while True:
            if self.peek().text == ".":
                self.advance()
                name = self.advance()
                if name.kind not in ("name", *_KEYWORDS):
                    raise DqlError(f"expected a field name after '.', found {name.text!r}")
                if self.peek().text == "(":
                    # A method call desugars to a function with the receiver first.
                    self.advance()
                    arguments = [node]
                    while self.peek().text != ")":
                        arguments.append(self.expression())
                        if self.peek().text == ",":
                            self.advance()
                    self.advance()
                    node = Call(name.text.casefold(), tuple(arguments))
                elif isinstance(node, Field):
                    node = Field(node.parts + (name.text,))
                else:
                    node = Binary(".", node, Literal(name.text))
            elif self.peek().text == "[":
                self.advance()
                index = self.expression()
                self.expect_text("]")
                node = Binary("index", node, index)
            else:
                return node

    def _primary(self):
        token = self.advance()
        if token.kind == "number":
            value = float(token.text) if "." in token.text else int(token.text)
            return Literal(value)
        if token.kind == "string":
            return Literal(_unescape(token.text[1:-1]))
        if token.kind == "true":
            return Literal(True)
        if token.kind == "false":
            return Literal(False)
        if token.kind == "null":
            return Literal(None)
        if token.text == "[":
            items = []
            while self.peek().text != "]":
                items.append(self.expression())
                if self.peek().text == ",":
                    self.advance()
            self.advance()
            return ListExpr(tuple(items))
        if token.text == "(":
            # A parenthesized lambda: (x) => expression
            if (
                self.peek().kind == "name"
                and self.tokens[self.position + 1].text == ")"
                and self.tokens[self.position + 2].text == "=>"
            ):
                parameter = self.advance().text
                self.advance()
                self.advance()
                return Lambda(parameter, self.expression())
            node = self.expression()
            self.expect_text(")")
            return node
        if token.kind == "name":
            if self.peek().text == "(":
                if token.text.casefold() == "dur":
                    return self._duration_call()
                self.advance()
                arguments = []
                while self.peek().text != ")":
                    arguments.append(self.expression())
                    if self.peek().text == ",":
                        self.advance()
                self.advance()
                return Call(token.text.casefold(), tuple(arguments))
            return Field((token.text,))
        raise DqlError(f"unexpected {token.text or 'end of input'!r}")

    def _duration_call(self):
        """`dur(14 days)` — the argument is its own tiny grammar, not an expression."""
        self.advance()
        amount = self.advance()
        if amount.kind != "number":
            raise DqlError("dur() expects a number and a unit")
        unit = self.advance()
        if unit.kind != "name":
            raise DqlError("dur() expects a unit after the number")
        self.expect_text(")")
        return Call("dur", (Literal(float(amount.text)), Literal(unit.text.casefold())))

    def expect_text(self, text: str) -> None:
        token = self.advance()
        if token.text != text:
            raise DqlError(f"expected {text!r}, found {token.text or 'end of input'!r}")


def _unescape(text: str) -> str:
    return text.replace('\\"', '"').replace("\\\\", "\\")


def parse_expression(text: str) -> object:
    """Parses one standalone expression, as used by inline evaluation."""
    parser = _Parser(_lex(text))
    node = parser.expression()
    if not parser.at_end():
        raise DqlError(f"unexpected trailing {parser.peek().text!r}")
    return node


def _parse_source(parser: _Parser) -> object:
    node = _parse_source_atom(parser)
    while parser.peek().kind in ("and", "or"):
        operator = parser.advance().kind
        node = SourceOp(operator, node, _parse_source_atom(parser))
    return node


def _parse_source_atom(parser: _Parser) -> object:
    token = parser.advance()
    if token.text in ("-", "!"):
        return SourceNot(_parse_source_atom(parser))
    if token.text == "(":
        node = _parse_source(parser)
        parser.expect_text(")")
        return node
    if token.kind == "string":
        return SourceFolder(_unescape(token.text[1:-1]))
    if token.kind == "tag":
        return SourceTag(token.text[1:])
    if token.text == "[":
        parser.expect_text("[")
        parser.expect_text("]")
        parser.expect_text("]")
        return SourceLink()
    raise DqlError(f"unsupported FROM source {token.text!r}")


def parse_query(text: str) -> Query:
    """Parses a full DQL block: the head, the source, and the data commands in order."""
    parser = _Parser(_lex(text))
    head = parser.advance()
    kind = head.text.casefold() if head.kind == "name" else head.kind
    if kind not in ("table", "list", "task"):
        raise DqlError(f"unsupported query type {head.text!r}")

    without_id = False
    if kind == "table" and parser.peek().kind == "without":
        parser.advance()
        if parser.peek().kind == "id":
            parser.advance()
            without_id = True

    commands = ("from", "where", "sort", "limit", "flatten", "group", "end")
    columns: list[Column] = []
    if kind in ("table", "list"):
        while parser.peek().kind not in commands:
            expression = parser.expression()
            header = _describe(expression)
            if parser.peek().kind == "as":
                parser.advance()
                alias = parser.advance()
                if alias.kind == "string":
                    header = _unescape(alias.text[1:-1])
                elif alias.kind == "name":
                    header = alias.text
                else:
                    raise DqlError("expected a column name after AS")
            columns.append(Column(expression, header))
            if parser.peek().text == ",":
                parser.advance()
        if kind == "list" and len(columns) > 1:
            raise DqlError("LIST takes at most one expression")

    source = None
    steps: list = []
    while not parser.at_end():
        token = parser.advance()
        if token.kind == "from":
            source = _parse_source(parser)
        elif token.kind == "where":
            steps.append(("where", parser.expression()))
        elif token.kind == "sort":
            keys = []
            while True:
                expression = parser.expression()
                descending = False
                if parser.peek().kind in ("asc", "desc"):
                    descending = parser.advance().kind == "desc"
                keys.append(SortKey(expression, descending))
                if parser.peek().text == ",":
                    parser.advance()
                    continue
                break
            steps.append(("sort", tuple(keys)))
        elif token.kind == "limit":
            limit = parser.advance()
            if limit.kind != "number":
                raise DqlError("LIMIT expects a number")
            steps.append(("limit", int(float(limit.text))))
        elif token.kind == "flatten":
            expression = parser.expression()
            alias = _describe(expression)
            if parser.peek().kind == "as":
                parser.advance()
                alias = parser.advance().text
            steps.append(("flatten", expression, alias))
        elif token.kind == "group":
            parser.expect("by")
            expression = parser.expression()
            alias = _describe(expression)
            if parser.peek().kind == "as":
                parser.advance()
                alias = parser.advance().text
            steps.append(("group", expression, alias))
        else:
            raise DqlError(f"unsupported command {token.text!r}")
    return Query(
        kind=kind,
        columns=tuple(columns),
        without_id=without_id,
        source=source,
        steps=tuple(steps),
    )


def _describe(expression) -> str:
    """A readable default column header for an unaliased expression."""
    if isinstance(expression, Field):
        return ".".join(expression.parts)
    if isinstance(expression, Call):
        return expression.name
    return "value"
