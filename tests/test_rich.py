import logging
import random
import re
import string

import pytest
from rich.pretty import Pretty

from logurich import init_logger, shutdown_logger


def generate_random_dict(k, depth=3):
    if depth <= 1:
        return {
            "".join(random.choices(string.ascii_letters, k=5)): random.randint(1, 100)
            for _ in range(k)
        }
    return {
        "".join(random.choices(string.ascii_letters, k=20)): generate_random_dict(
            k, depth - 1
        )
        for _ in range(k)
    }


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "INFO", "enqueue": True}],
    indirect=True,
)
def test_renderables_are_prefixed(logger, buffer):
    logger.rich(
        "INFO",
        Pretty(generate_random_dict(5, 5), max_length=3, max_depth=3),
        title="Rich Test",
    )
    shutdown_logger()

    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    assert lines
    for line in lines:
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| INFO", line)


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}],
    indirect=True,
)
def test_render_width_affects_output(logger, buffer):
    wide_text = " ".join(["wrap"] * 60)

    logger.rich("INFO", wide_text, title="Wrapped output", width=60)
    narrow_output = buffer.getvalue()

    buffer.truncate(0)
    buffer.seek(0)

    logger.rich("INFO", wide_text, title="Wrapped output", width=110)
    wide_output = buffer.getvalue()

    assert narrow_output
    assert wide_output
    assert narrow_output != wide_output
    assert "…" in narrow_output
    assert "…" not in wide_output


def test_named_stdlib_logger_has_rich_method(buffer):
    init_logger("INFO", enqueue=False)

    named_logger = logging.getLogger("pkg.worker")
    assert hasattr(named_logger, "ctx")
    assert hasattr(named_logger, "rich")

    named_logger.rich("INFO", "named body", title="Named title")
    shutdown_logger()

    output = buffer.getvalue()
    assert "Named title" in output
    assert "named body" in output


def test_root_logger_has_rich_method(buffer):
    init_logger("INFO", enqueue=False)

    root_logger = logging.getLogger()
    assert hasattr(root_logger, "ctx")
    assert hasattr(root_logger, "rich")

    root_logger.rich("INFO", "root body", title="Root title")
    shutdown_logger()

    output = buffer.getvalue()
    assert "Root title" in output
    assert "root body" in output
