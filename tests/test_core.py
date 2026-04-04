import json
import logging

import pytest
from rich.panel import Panel

from logurich import (
    ctx,
    global_context_configure,
    global_context_set,
    init_logger,
    shutdown_logger,
)


@pytest.mark.parametrize(
    "logger",
    [{"level": "INFO", "enqueue": False}, {"level": "INFO", "enqueue": True}],
    indirect=True,
)
def test_level_info(logger, buffer):
    logger.info("Hello, %s!", "world")
    logger.debug("Debug, world!")
    shutdown_logger()
    output = buffer.getvalue()
    assert "Hello, world!" in output
    assert "Debug, world!" not in output


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_level_debug(logger, buffer):
    logger.info("Hello, %s!", "world")
    logger.debug("Debug, world!")
    shutdown_logger()
    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    assert "Hello, world!" in lines[0]
    assert "Debug, world!" in lines[1]


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_global_context_configure(logger, buffer):
    with global_context_configure(exec_id=ctx("id_123", style="yellow")):
        logger.info("Hello, world!")
        logger.debug("Debug, world!")
    shutdown_logger()
    assert all("id_123" in line for line in buffer.getvalue().splitlines() if line)


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}],
    indirect=True,
)
def test_global_context_configure_restores_previous(logger, buffer):
    with global_context_configure(exec_id=ctx("outer_ctx", style="yellow")):
        logger.info("outer message")
        with global_context_configure(exec_id=ctx("inner_ctx", style="cyan")):
            logger.info("inner message")
        logger.info("outer message again")
    logger.info("plain message")
    shutdown_logger()

    log_lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    assert "outer_ctx" in log_lines[0]
    assert "inner_ctx" not in log_lines[0]
    assert "inner_ctx" in log_lines[1]
    assert "outer_ctx" not in log_lines[1]
    assert "outer_ctx" in log_lines[2]
    assert "inner_ctx" not in log_lines[2]
    assert "outer_ctx" not in log_lines[3]
    assert "inner_ctx" not in log_lines[3]


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_per_call_context_via_extra(logger, buffer):
    logger.info(
        "bound message",
        extra={
            "context": {
                "session": ctx("sess-42", style="cyan", show_key=True),
            }
        },
    )
    shutdown_logger()
    output = buffer.getvalue()
    assert "session=sess-42" in output


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_global_context_set(logger, buffer):
    global_context_set(exec_id=ctx("id_123", style="yellow"))
    logger.info("Hello, world!")
    logger.debug("Debug, world!")
    shutdown_logger()
    assert all("id_123" in line for line in buffer.getvalue().splitlines() if line)


@pytest.mark.parametrize(
    "enqueue",
    [False, True],
)
def test_logurich_serialize_env(monkeypatch, enqueue, buffer):
    monkeypatch.setenv("LOGURICH_SERIALIZE", "1")
    monkeypatch.setenv("LOGURICH_EXTRA_APP", "serialize-test")
    init_logger("DEBUG", enqueue=enqueue)
    logging.getLogger("serialize.test").info(
        "Serialized %s",
        "output",
        extra={"context": {"request_id": ctx("req-42")}},
    )
    shutdown_logger()

    log_lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    assert log_lines, "No serialized output captured"
    payload = json.loads(log_lines[0])
    assert "Serialized output" in payload["text"]
    assert payload["text"].endswith("\n")
    assert payload["record"]["message"] == "Serialized output"
    assert payload["record"]["level"]["name"] == "INFO"
    assert payload["record"]["level"]["no"] == logging.INFO
    assert payload["record"]["name"] == "serialize.test"
    assert payload["record"]["extra"]["APP"] == "serialize-test"
    assert payload["record"]["extra"]["request_id"] == "req-42"
    assert payload["record"]["exception"] is None


def test_logurich_serialize_rich_payload_goes_to_text(monkeypatch, buffer):
    monkeypatch.setenv("LOGURICH_SERIALIZE", "1")
    init_logger("INFO", enqueue=False)

    logging.getLogger("serialize.rich").rich(
        "INFO",
        Panel("Panel content", border_style="green"),
        title="Rich payload",
    )
    shutdown_logger()

    payload = json.loads(buffer.getvalue().splitlines()[0])
    assert "Rich payload" in payload["text"]
    assert "Panel content" in payload["text"]
    assert payload["record"]["message"] == "Rich payload"
    assert "rendered" not in payload["record"]


def test_logurich_serialize_exception_object(monkeypatch, buffer):
    monkeypatch.setenv("LOGURICH_SERIALIZE", "1")
    init_logger("INFO", enqueue=False)

    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("serialize.exc").exception("Failed")

    shutdown_logger()

    payload = json.loads(buffer.getvalue().splitlines()[0])
    assert payload["record"]["exception"]["type"] == "ValueError"
    assert payload["record"]["exception"]["value"] == "boom"
    assert "ValueError: boom" in payload["record"]["exception"]["traceback"]
    assert "Failed" in payload["text"]


def test_level_by_module_filters_named_loggers(buffer):
    init_logger(
        "INFO",
        enqueue=False,
        level_by_module={"pkg.worker": "DEBUG"},
    )
    worker_logger = logging.getLogger("pkg.worker")
    other_logger = logging.getLogger("pkg.other")

    worker_logger.debug("worker debug")
    other_logger.debug("other debug")
    worker_logger.info("worker info")
    shutdown_logger()

    output = buffer.getvalue()
    assert "worker debug" in output
    assert "worker info" in output
    assert "other debug" not in output


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_exception_logging_preserves_traceback(logger, buffer):
    try:
        raise ZeroDivisionError("boom")
    except ZeroDivisionError:
        logger.exception("Computation failed")

    shutdown_logger()
    output = buffer.getvalue()
    assert "Computation failed" in output
    assert "ZeroDivisionError" in output
