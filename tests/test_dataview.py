"""The Dataview engine: expressions, queries, and the shapes real vaults use."""

import datetime

import pytest

from solander.core.dataview import DataviewEngine, Evaluator, Row
from solander.core.dql import DqlError, parse_expression
from solander.core.graph import VaultGraph


def evaluate(text: str, props: dict | None = None, this: dict | None = None):
    row = Row(props or {}, {})
    this_row = Row(this, {}) if this is not None else row
    return Evaluator(this_row).evaluate(parse_expression(text), row)


# -- expressions ------------------------------------------------------------


def test_arithmetic_and_precedence():
    assert evaluate("1 + 2 * 3") == 7
    assert evaluate("(1 + 2) * 3") == 9
    assert evaluate("10 / 4") == 2.5


def test_string_concat_coerces_numbers():
    assert evaluate('"$" + round(1234 / 1000, 1) + "K"') == "$1.2K"


def test_null_comparisons_match_dataview():
    assert evaluate("missing = null") is True
    assert evaluate("missing != null") is False
    assert evaluate("missing > 3") is False
    assert evaluate('default(missing, "x")') == "x"


def test_choice_nesting():
    props = {"Priority": 4}
    text = 'choice(Priority = 5, "★★★★★", choice(Priority = 4, "★★★★☆", "unrated"))'
    assert evaluate(text, props) == "★★★★☆"


def test_boolean_keywords_and_symbols_are_equivalent():
    props = {"a": 1, "b": 0}
    assert evaluate("a and !b", props) is True
    assert evaluate("a & !b", props) is True
    assert evaluate("b or a", props) == 1


def test_date_arithmetic_with_durations():
    props = {"date": "2026-09-01"}
    assert evaluate("date(date) - dur(14 days)", props) == datetime.date(2026, 8, 18)
    assert evaluate('date >= date("2026-08-30")', props) is True


def test_dateformat_uses_luxon_tokens():
    assert evaluate('dateformat(date("2026-09-01"), "ccc")') == "Tue"
    assert evaluate('dateformat(date("2026-09-01"), "yyyy-MM-dd")') == "2026-09-01"
    assert evaluate('dateformat(date("2026-09-01"), "LLL")') == "Sep"
    assert evaluate('dateformat(date("2026-09-01"), "yyyy-LL-dd")') == "2026-09-01"


def test_date_keywords_are_answered_rather_than_read_as_fields():
    """A bare keyword parses as a field name, and a missing field makes every
    comparison against it false — so a recency query returned nothing at all."""
    assert evaluate("date(today)") == datetime.date.today()
    assert evaluate("date(yesterday)") == datetime.date.today() - datetime.timedelta(days=1)
    assert evaluate("date(tomorrow)") == datetime.date.today() + datetime.timedelta(days=1)
    assert isinstance(evaluate("date(now)"), datetime.datetime)


def test_a_recency_window_selects_a_recent_note():
    recent = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
    stale = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
    assert evaluate("date(when) >= date(today) - dur(30 days)", {"when": recent}) is True
    assert evaluate("date(when) >= date(today) - dur(30 days)", {"when": stale}) is False


def test_a_property_named_today_is_still_reachable():
    """The keyword is only read as one inside `date()`; elsewhere it is a field."""
    assert evaluate("today", {"today": "busy"}) == "busy"


def test_field_lookup_is_case_insensitive():
    assert evaluate("status", {"Status": "Open"}) == "Open"


def test_this_reaches_the_current_note():
    assert evaluate("this.start", {}, this={"start": "2026-09-01"}) == "2026-09-01"


def test_filter_with_a_lambda():
    props = {"xs": [1, 5, 10]}
    assert evaluate("filter(xs, (x) => x > 4)", props) == [5, 10]


def test_functions_used_by_the_vault():
    assert evaluate('length([1, 2, 3])') == 3
    assert evaluate('lower("ABC")') == "abc"
    assert evaluate('contains("Hunt/Applied", "applied")') is True
    assert evaluate('startswith("01 Journal/Notes/2026", "01 Journal")') is True
    assert evaluate("sum([1, 2, 3])") == 6
    assert evaluate('striptime(date("2026-09-01T10:30"))') == datetime.date(2026, 9, 1)


def test_unknown_function_is_a_named_refusal():
    with pytest.raises(DqlError):
        evaluate("regexmatch('a', 'b')")


# -- queries over the fixture vault -----------------------------------------


@pytest.fixture
def engine(vault, vault_dir):
    (vault_dir / "Projects" / "Beta.md").write_text(
        "---\nstatus: open\npriority: 2\n---\n# Beta\n\n- [ ] open task\n- [x] done task\n"
    )
    (vault_dir / "Projects" / "Gamma.md").write_text(
        "---\nstatus: done\npriority: 5\n---\n# Gamma\n"
    )
    vault.reindex()
    return DataviewEngine(VaultGraph.build(vault))


def run(engine, query, this="Index.md"):
    return engine.run_query(query, this)


def test_table_from_folder_with_where_and_sort(engine):
    markup = run(engine, 'TABLE priority FROM "Projects" WHERE status SORT priority DESC')
    assert markup.index("Gamma") < markup.index("Beta")
    assert "<th>File</th>" in markup and "<th>priority</th>" in markup


def test_without_id_and_aliases(engine):
    markup = run(engine, 'TABLE WITHOUT ID file.link AS "Note" FROM "Projects" WHERE status')
    assert "<th>File</th>" not in markup
    assert "<th>Note</th>" in markup
    assert 'href="reader:///note/Projects/Beta.md"' in markup


def test_list_query(engine):
    markup = run(engine, 'LIST FROM "Projects" WHERE status = "open"')
    assert "<ul>" in markup and "Beta" in markup and "Gamma" not in markup


def test_task_query(engine):
    markup = run(engine, 'TASK FROM "Projects" WHERE !completed')
    assert "open task" in markup and "done task" not in markup
    assert 'type="checkbox"' in markup


def test_flatten_and_group_by(engine):
    markup = run(
        engine,
        'TABLE WITHOUT ID topic, length(rows) AS n FROM "" '
        "FLATTEN file.tags AS topic GROUP BY topic SORT length(rows) DESC",
    )
    assert "#home" in markup


def test_source_tag_and_negation(engine):
    markup = run(engine, 'LIST FROM "Projects" and -#nothing WHERE status')
    assert "Beta" in markup


def test_limit(engine):
    markup = run(engine, 'LIST FROM "Projects" SORT file.name ASC LIMIT 1')
    assert markup.count("<li>") == 1


def test_unsupported_query_raises_with_reason(engine):
    with pytest.raises(DqlError):
        run(engine, "CALENDAR file.day")


def test_inline_expression(engine):
    assert engine.run_inline("this.title", "Index.md") == "Index"
    assert engine.run_inline("length(this.tags)", "Index.md") == "1"


def test_result_values_are_escaped(engine, vault, vault_dir):
    (vault_dir / "Projects" / "Hostile.md").write_text(
        '---\nstatus: "<script>alert(1)</script>"\n---\n# H\n'
    )
    vault.reindex()
    hostile = DataviewEngine(VaultGraph.build(vault))
    markup = run(hostile, 'TABLE status FROM "Projects" WHERE status')
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup


def test_bracket_access_reaches_spaced_field_names():
    assert evaluate('this["Decided On"]', {}, this={"Decided On": "yes"}) == "yes"
    assert evaluate("xs[1]", {"xs": [10, 20]}) == 20
    assert evaluate("xs[9]", {"xs": [10, 20]}) is None


def test_if_typeof_and_tonumber():
    assert evaluate('if(1 > 0, "a", "b")') == "a"
    assert evaluate('typeof(date("2026-09-01"))') == "date"
    assert evaluate('tonumber("4")') == 4.0


def test_from_empty_link_means_backlinks_of_this(engine):
    markup = run(engine, "LIST FROM [[]]", this="Projects/Alpha.md")
    assert "Index" in markup
    assert "Gamma" not in markup
