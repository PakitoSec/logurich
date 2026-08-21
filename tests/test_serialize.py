import time

import pytest
from rich.layout import Layout
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from logurich.serialize import MAX_DEPTH, serialize_renderables


def build_table(rows=1):
    table = Table(title="Metrics")
    table.add_column("Name", justify="center", style="green")
    table.add_column("Value")
    for index in range(rows):
        table.add_row(f"row-{index}", "42")
    return table


def test_default_mode_matches_documented_shape():
    payload = serialize_renderables((build_table(),))
    assert payload == [
        {
            "type": "table",
            "title": "Metrics",
            "columns": ["Name", "Value"],
            "rows": [["row-0", "42"]],
        }
    ]


def test_default_mode_omits_style_metadata():
    payload = serialize_renderables((Panel(Text("x"), title="T"), Rule("r")))
    assert payload[0] == {
        "type": "panel",
        "title": "T",
        "subtitle": None,
        "content": {"type": "text", "text": "x"},
    }
    assert payload[1] == {"type": "rule", "title": "r"}


def test_max_rows_none_keeps_every_row():
    payload = serialize_renderables((build_table(rows=150),), max_rows=None)[0]
    assert len(payload["rows"]) == 150
    assert "truncated" not in payload


def test_max_rows_truncates_and_flags():
    payload = serialize_renderables((build_table(rows=5),), max_rows=2)[0]
    assert len(payload["rows"]) == 2
    assert payload["truncated"] is True


def test_max_depth_falls_back_to_rendered_text():
    nested = Panel(Panel(Panel(Text("deep"))))
    payload = serialize_renderables((nested,), max_depth=1)
    innermost = payload[0]["content"]["content"]
    assert innermost["truncated"] is True
    assert innermost["type"] == "text"


def test_max_depth_default_is_unchanged():
    assert MAX_DEPTH == 4


def test_styles_emit_spans():
    payload = serialize_renderables(
        (Text.from_markup("[bold red]hot[/]"),), styles=True
    )
    assert payload[0]["text"] == "hot"
    assert payload[0]["spans"] == [{"start": 0, "end": 3, "style": "bold red"}]


def test_styles_extract_link():
    text = Text.from_markup("[link=http://example.test/x]doc[/link]")
    span = serialize_renderables((text,), styles=True)[0]["spans"][0]
    assert span["link"] == "http://example.test/x"


def test_styles_omit_spans_when_unstyled():
    payload = serialize_renderables((Text("plain"),), styles=True)
    assert payload[0] == {"type": "text", "text": "plain"}


def test_styles_expose_table_metadata():
    payload = serialize_renderables((build_table(),), styles=True)[0]
    assert payload["columns"][0] == {
        "header": {"type": "text", "text": "Name"},
        "justify": "center",
        "no_wrap": False,
        "style": "green",
    }
    assert payload["rows"][0][0] == {"type": "text", "text": "row-0"}
    assert payload["show_header"] is True


def test_styles_expose_panel_and_rule_metadata():
    panel, rule = serialize_renderables(
        (Panel(Text("x"), border_style="blue"), Rule("r", style="dim")), styles=True
    )
    assert panel["border_style"] == "blue"
    assert panel["title_align"] == "center"
    assert rule["style"] == "dim"
    assert rule["align"] == "center"


def test_invalid_style_does_not_raise():
    text = Text("x")
    text.stylize("definitely-not-a-style", 0, 1)
    payload = serialize_renderables((text,), styles=True)
    assert payload[0]["text"] == "x"


def test_layout_serialises_tree_and_leaves():
    layout = Layout(name="root")
    layout.split_row(Layout(Text("a"), name="left"), Layout(name="right"))
    payload = serialize_renderables((layout,), styles=True)[0]
    assert payload["type"] == "layout"
    assert payload["direction"] == "row"
    assert payload["children"][0]["content"] == {"type": "text", "text": "a"}
    assert payload["children"][1]["content"] is None


def test_layout_reports_visibility():
    layout = Layout(Text("a"), name="hidden")
    layout.visible = False
    assert serialize_renderables((layout,))[0]["visible"] is False


@pytest.mark.parametrize("rows", [500])
def test_large_table_serialisation_stays_fast(rows):
    table = build_table(rows=rows)
    start = time.perf_counter()
    serialize_renderables((table,), max_rows=None, styles=True)
    assert time.perf_counter() - start < 2.0
