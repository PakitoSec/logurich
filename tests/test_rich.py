import inspect
import json
import logging
import re

import pytest
from rich.console import Group
from rich.logging import RichHandler
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from logurich import LogurichLogger, get_logger, init_logger, shutdown_logger


def build_table() -> Table:
    table = Table(title="Metrics")
    table.add_column("Name")
    table.add_column("Value")
    table.add_row("requests", "42")
    return table


@pytest.mark.parametrize("enqueue", [False, True])
def test_rich_accepts_multiple_live_renderables(enqueue, buffer):
    init_logger("INFO", enqueue=enqueue)
    logger = get_logger("tests.rich")
    logger.rich(
        "INFO",
        Panel("Service ready", border_style="green"),
        build_table(),
        title="Startup",
    )
    shutdown_logger()

    output = buffer.getvalue()
    assert "Startup" in output
    assert "Service ready" in output
    assert "Metrics" in output
    assert "requests" in output


def test_bound_logger_keeps_rich_method(buffer):
    init_logger("INFO", enqueue=False)
    logger = get_logger("tests.bound-rich").bind(module="api")

    assert isinstance(logger, LogurichLogger)
    logger.rich("INFO", Panel("Ready"), title="Bound")
    shutdown_logger()

    output = buffer.getvalue()
    assert "module=api" in output
    assert "Bound" in output
    assert "Ready" in output


def test_rich_numeric_custom_level(buffer):
    logging.addLevelName(35, "NOTICE")
    init_logger("INFO", enqueue=False)
    get_logger("tests.rich-level").rich(35, "notice body", title="notice")
    shutdown_logger()

    output = buffer.getvalue()
    assert "NOTICE" in output
    assert "notice body" in output


def test_rich_rejects_invalid_level_and_width():
    logger = get_logger("tests.invalid-rich")
    with pytest.raises(ValueError, match="Unknown log level"):
        logger.rich("UNKNOWN", "body")
    with pytest.raises(ValueError, match="width"):
        logger.rich("INFO", "body", width=0)


def test_render_width_affects_output(buffer):
    init_logger("INFO", enqueue=False)
    logger = get_logger("tests.width")
    wide_text = " ".join(["wrap"] * 60)

    logger.rich("INFO", wide_text, title="Wrapped output", width=60)
    narrow_output = buffer.getvalue()
    buffer.truncate(0)
    buffer.seek(0)
    logger.rich("INFO", wide_text, title="Wrapped output", width=110)
    wide_output = buffer.getvalue()
    shutdown_logger()

    assert narrow_output != wide_output
    assert "…" in narrow_output
    assert "…" not in wide_output


def test_prefix_false_omits_prefix_from_renderable(buffer):
    init_logger("INFO", enqueue=False)
    get_logger("tests.prefix").rich("INFO", "body-only", prefix=False)
    shutdown_logger()

    line = next(line for line in buffer.getvalue().splitlines() if "body-only" in line)
    assert line == "body-only"


def test_end_is_preserved(buffer):
    init_logger("INFO", enqueue=False)
    logger = get_logger("tests.end")
    logger.rich("INFO", "first", prefix=False, end="")
    logger.rich("INFO", "second", prefix=False, end="")
    shutdown_logger()
    assert buffer.getvalue().endswith("firstsecond")


def test_end_is_preserved_in_text_file(tmp_path, buffer):
    init_logger(
        "INFO",
        log_filename="end.log",
        log_folder=str(tmp_path),
        rotation=None,
        enqueue=False,
    )
    get_logger("tests.file-end").rich("INFO", "tail", prefix=False, end="")
    shutdown_logger()
    assert (tmp_path / "end.log").read_text().endswith("tail")


def test_json_console_uses_newline_framing_when_end_is_empty(buffer):
    init_logger("INFO", console="json", enqueue=False)
    logger = get_logger("tests.json-console-end")
    logger.rich("INFO", "first", prefix=False, end="")
    logger.rich("INFO", "second", prefix=False, end="")
    shutdown_logger()

    output = buffer.getvalue()
    payloads = [json.loads(line) for line in output.splitlines()]
    assert output.endswith("\n")
    assert len(payloads) == 2
    assert payloads[0]["text"].endswith("first")
    assert payloads[1]["text"].endswith("second")
    assert not payloads[0]["text"].endswith("\n")
    assert not payloads[1]["text"].endswith("\n")


def test_json_file_uses_newline_framing_when_end_is_empty(tmp_path, buffer):
    init_logger(
        "INFO",
        log_filename="end.jsonl",
        log_folder=str(tmp_path),
        console="plain",
        file="json",
        rotation=None,
        enqueue=False,
    )
    logger = get_logger("tests.json-file-end")
    logger.rich("INFO", "first", prefix=False, end="")
    logger.rich("INFO", "second", prefix=False, end="")
    shutdown_logger()

    output = (tmp_path / "end.jsonl").read_text()
    payloads = [json.loads(line) for line in output.splitlines()]
    assert output.endswith("\n")
    assert len(payloads) == 2
    assert payloads[0]["text"].endswith("first")
    assert payloads[1]["text"].endswith("second")
    assert not payloads[0]["text"].endswith("\n")
    assert not payloads[1]["text"].endswith("\n")


def test_json_serializes_table_structurally(buffer):
    init_logger("INFO", console="json", enqueue=False)
    get_logger("tests.json-table").rich("INFO", build_table(), title="report")
    shutdown_logger()

    payload = json.loads(buffer.getvalue().splitlines()[0])
    assert payload["record"]["renderables"] == [
        {
            "type": "table",
            "title": "Metrics",
            "columns": ["Name", "Value"],
            "rows": [["requests", "42"]],
        }
    ]
    assert payload["record"]["message"] == "report"
    assert "┏" not in payload["text"]
    assert "┏" not in json.dumps(payload)


def test_json_serializes_nested_panel(buffer):
    init_logger("INFO", console="json", enqueue=False)
    get_logger("tests.json-panel").rich(
        "INFO", Panel(build_table(), title="wrap", subtitle="sub")
    )
    shutdown_logger()

    payload = json.loads(buffer.getvalue().splitlines()[0])
    assert payload["record"]["renderables"] == [
        {
            "type": "panel",
            "title": "wrap",
            "subtitle": "sub",
            "content": {
                "type": "table",
                "title": "Metrics",
                "columns": ["Name", "Value"],
                "rows": [["requests", "42"]],
            },
        }
    ]


def test_json_serializes_tree_syntax_and_group(buffer):
    tree = Tree("root")
    tree.add("branch").add("leaf")
    init_logger("INFO", console="json", enqueue=False)
    get_logger("tests.json-misc").rich(
        "INFO",
        tree,
        Syntax("print(1)", "python"),
        Group(Text("a"), Rule("done")),
    )
    shutdown_logger()

    renderables = json.loads(buffer.getvalue().splitlines()[0])["record"]["renderables"]
    assert renderables == [
        {
            "type": "tree",
            "label": "root",
            "children": [
                {
                    "type": "tree",
                    "label": "branch",
                    "children": [{"type": "tree", "label": "leaf", "children": []}],
                }
            ],
        },
        {"type": "syntax", "lexer": "python", "code": "print(1)"},
        {
            "type": "group",
            "items": [
                {"type": "text", "text": "a"},
                {"type": "rule", "title": "done"},
            ],
        },
    ]


def test_json_falls_back_to_text_and_repr(buffer):
    class Custom:
        def __rich_console__(self, console, options):
            yield Text("custom body")

    marker = object()
    init_logger("INFO", console="json", enqueue=False)
    get_logger("tests.json-fallback").rich("INFO", Custom(), marker)
    shutdown_logger()

    renderables = json.loads(buffer.getvalue().splitlines()[0])["record"]["renderables"]
    assert renderables[0] == {"type": "text", "text": "custom body"}
    assert renderables[1] == {"type": "object", "repr": repr(marker)}


def test_json_omits_renderables_when_only_text(buffer):
    init_logger("INFO", console="json", enqueue=False)
    get_logger("tests.json-text-only").rich("INFO", "just text", prefix=False)
    shutdown_logger()

    payload = json.loads(buffer.getvalue().splitlines()[0])
    assert "renderables" not in payload["record"]
    assert payload["text"] == "just text\n"


def test_json_file_serializes_renderables_structurally(tmp_path, buffer):
    init_logger(
        "INFO",
        log_filename="structured.jsonl",
        log_folder=str(tmp_path),
        console="plain",
        file="json",
        rotation=None,
        enqueue=False,
    )
    get_logger("tests.json-file-table").rich("INFO", build_table())
    shutdown_logger()

    payload = json.loads((tmp_path / "structured.jsonl").read_text().splitlines()[0])
    assert payload["record"]["renderables"][0]["type"] == "table"
    assert "┏" not in json.dumps(payload)


def test_rich_stacklevel_points_to_caller(buffer):
    init_logger("INFO", console="json", enqueue=False)
    logger = get_logger("tests.stacklevel")
    expected_line = inspect.currentframe().f_lineno + 1
    logger.rich("INFO", "body", title="source")
    shutdown_logger()

    payload = json.loads(buffer.getvalue().splitlines()[0])
    assert payload["record"]["line"] == expected_line
    assert payload["record"]["function"] == "test_rich_stacklevel_points_to_caller"


def test_rich_console_mode_uses_rich_handler(buffer):
    init_logger("INFO", console="rich", enqueue=False)
    get_logger("tests.rich-console").rich(
        "INFO", Panel("Live panel", border_style="magenta"), title="Title"
    )
    shutdown_logger()

    output = buffer.getvalue()
    assert "Live panel" in output
    assert "Title" in output


def test_plain_rich_output_has_log_prefix(buffer):
    init_logger("INFO", enqueue=False)
    get_logger("tests.prefix-format").rich("INFO", "body", title="title")
    shutdown_logger()

    lines = [line for line in buffer.getvalue().splitlines() if line]
    assert all(
        re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| INFO", line)
        for line in lines
    )


def test_stdlib_loggers_do_not_have_rich_methods():
    assert not hasattr(logging.getLogger("third.party.rich"), "rich")
    assert not hasattr(logging.getLogger(), "rich")


def test_rich_console_falls_back_to_plain_without_the_rich_layout(monkeypatch, buffer):
    """A Rich release dropping ``_log_render`` must not silence logging."""

    rich_handler_init = RichHandler.__init__

    def init_without_log_render(self, *args, **kwargs):
        rich_handler_init(self, *args, **kwargs)
        del self._log_render

    monkeypatch.setattr(RichHandler, "__init__", init_without_log_render)

    with pytest.warns(UserWarning, match="falling back to console='plain'"):
        init_logger("INFO", console="rich", enqueue=False)
    get_logger("tests.rich-fallback").info("still logging")
    shutdown_logger()

    assert "still logging" in buffer.getvalue()
