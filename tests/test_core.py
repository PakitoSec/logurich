import json
import logging
import threading
from types import MappingProxyType

import pytest
from rich.panel import Panel

from logurich import (
    BoundLogger,
    ctx,
    global_context_configure,
    global_context_set,
    init_logger,
    shutdown_logger,
)
from logurich import (
    logger as exported_logger,
)
from logurich.console import rich_configure_console
from logurich.struct import logger_state


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


def test_init_logger_registers_shutdown_hooks_once(monkeypatch):
    registered: list[object] = []
    thread_registered: list[object] = []
    register_threading_atexit = getattr(threading, "_register_atexit", None)

    monkeypatch.setitem(logger_state, "atexit_registered", False)
    monkeypatch.setitem(logger_state, "threading_atexit_registered", False)
    monkeypatch.setattr("logurich.core.atexit.register", registered.append)
    if register_threading_atexit is None:
        monkeypatch.delattr("logurich.core.threading._register_atexit", raising=False)
    else:
        monkeypatch.setattr(
            "logurich.core.threading._register_atexit", thread_registered.append
        )

    init_logger("INFO", enqueue=False)
    shutdown_logger()
    init_logger("INFO", enqueue=False)
    shutdown_logger()

    assert registered == [shutdown_logger]
    if register_threading_atexit is None:
        assert thread_registered == []
    else:
        assert thread_registered == [shutdown_logger]


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
def test_logger_contextualize_alias(logger, buffer):
    with logger.contextualize(exec_id=logger.ctx("id_123", style="yellow")):
        logger.info("Hello, world!")
        logger.debug("Debug, world!")
    shutdown_logger()
    assert all("id_123" in line for line in buffer.getvalue().splitlines() if line)


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


def test_logger_ctx_matches_module_helper():
    assert exported_logger.ctx("demo", style="yellow", show_key=True) == ctx(
        "demo", style="yellow", show_key=True
    )


def test_named_logger_ctx_value_renders(buffer):
    init_logger("INFO", enqueue=False)

    named_logger = logging.getLogger("pkg.worker")
    named_logger.info(
        "named logger context",
        extra={
            "context": {
                "module": named_logger.ctx("MDI-API", style="yellow", show_key=True),
            }
        },
    )
    shutdown_logger()

    output = buffer.getvalue()
    assert "module=MDI-API" in output


def test_root_logger_ctx_value_renders(buffer):
    init_logger("INFO", enqueue=False)

    root_logger = logging.getLogger()
    root_logger.info(
        "root logger context",
        extra={
            "context": {
                "app": root_logger.ctx("root-app", style="cyan", show_key=True),
            }
        },
    )
    shutdown_logger()

    output = buffer.getvalue()
    assert "app=root-app" in output


def test_root_logger_contextualize(buffer):
    init_logger("INFO", enqueue=False)

    root_logger = logging.getLogger()
    with root_logger.contextualize(
        app=root_logger.ctx("root-app", style="cyan", show_key=True)
    ):
        root_logger.info("root logger context")
    shutdown_logger()

    output = buffer.getvalue()
    assert "app=root-app" in output


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
    assert payload["record"]["message"].startswith("Rich payload\n")
    assert "Panel content" in payload["record"]["message"]
    assert not payload["record"]["message"].endswith("\n")
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


def test_logurich_serialize_stdlib_extra_payload(monkeypatch, buffer):
    monkeypatch.setenv("LOGURICH_SERIALIZE", "1")
    init_logger("INFO", enqueue=False)

    logging.getLogger("serialize.extra").info(
        "Serialized extra",
        extra={"user": "alice", "action": "test"},
    )
    shutdown_logger()

    payload = json.loads(buffer.getvalue().splitlines()[0])
    assert payload["record"]["message"] == "Serialized extra"
    assert payload["record"]["extra"]["user"] == "alice"
    assert payload["record"]["extra"]["action"] == "test"


def test_single_line_messages_preserve_full_text_with_soft_wrap(buffer):
    rich_configure_console(file=buffer, width=65)
    init_logger("INFO", enqueue=False)

    logging.getLogger("api").info(
        "Handling request",
        extra={
            "context": {"API": ctx("API"), "request_id": ctx("req-99", show_key=True)}
        },
    )
    shutdown_logger()

    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1
    assert "Handling request" in lines[0]
    assert "…" not in lines[0]


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


# ── bind() tests ─────────────────────────────────────────────────────


def test_bind_returns_bound_logger(buffer):
    init_logger("INFO", enqueue=False)
    bound = exported_logger.bind(module=ctx("PM-API", style="magenta"))
    assert isinstance(bound, BoundLogger)
    # Original logger is not a BoundLogger (not mutated).
    assert not isinstance(exported_logger, BoundLogger)
    shutdown_logger()


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_bind_context_appears_in_logs(logger, buffer):
    bound = logger.bind(module=ctx("PM-API", style="magenta", show_key=True))
    bound.info("bound message")
    shutdown_logger()
    output = buffer.getvalue()
    assert "module=PM-API" in output


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_bind_chaining(logger, buffer):
    bound = logger.bind(app=ctx("myapp", style="green", show_key=True)).bind(
        module=ctx("PM-API", style="magenta", show_key=True)
    )
    bound.info("chained")
    shutdown_logger()
    output = buffer.getvalue()
    assert "app=myapp" in output
    assert "module=PM-API" in output


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_bind_per_call_overrides_bound(logger, buffer):
    bound = logger.bind(module=ctx("PM-API", style="magenta", show_key=True))
    bound.info(
        "overridden",
        extra={"context": {"module": ctx("OVERRIDE", style="cyan", show_key=True)}},
    )
    shutdown_logger()
    output = buffer.getvalue()
    assert "module=OVERRIDE" in output
    assert "PM-API" not in output


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}],
    indirect=True,
)
def test_bind_with_global_context(logger, buffer):
    with global_context_configure(
        global_key=ctx("global_val", style="yellow", show_key=True)
    ):
        bound = logger.bind(bound_key=ctx("bound_val", style="cyan", show_key=True))
        bound.info("merged")
    shutdown_logger()
    output = buffer.getvalue()
    assert "global_key=global_val" in output
    assert "bound_key=bound_val" in output


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_bound_logger_contextualize_with_bound_context(logger, buffer):
    bound = logger.bind(module=ctx("PM-API", style="magenta", show_key=True))

    with bound.contextualize(
        request_id=bound.ctx("req-42", style="cyan", show_key=True)
    ):
        bound.info("merged")
    shutdown_logger()

    output = buffer.getvalue()
    assert "module=PM-API" in output
    assert "request_id=req-42" in output


def test_bound_logger_ctx_method(buffer):
    init_logger("INFO", enqueue=False)
    bound = exported_logger.bind(module=ctx("PM-API", style="magenta"))
    assert bound.ctx("demo", style="yellow", show_key=True) == ctx(
        "demo", style="yellow", show_key=True
    )
    shutdown_logger()


def test_bound_logger_rich_method(buffer):
    init_logger("INFO", enqueue=False)
    bound = exported_logger.bind(module=ctx("PM-API", style="magenta"))
    bound.rich("INFO", Panel("Rich from bound logger"), title="bound-rich")
    shutdown_logger()
    output = buffer.getvalue()
    assert "Rich from bound logger" in output


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_bind_process_copies_reused_extra_mapping(logger):
    shared_extra = {"context": {}}

    bound_app = logger.bind(app=ctx("myapp", style="green", show_key=True))
    _, first_kwargs = bound_app.process("first", {"extra": shared_extra})

    bound_module = logger.bind(module=ctx("PM-API", style="magenta", show_key=True))
    _, second_kwargs = bound_module.process("second", {"extra": shared_extra})

    assert first_kwargs["extra"] is not shared_extra
    assert second_kwargs["extra"] is not shared_extra
    assert shared_extra == {"context": {}}
    assert set(first_kwargs["extra"]["context"]) == {"context::app"}
    assert set(second_kwargs["extra"]["context"]) == {"context::module"}


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_bind_process_accepts_extra_none(logger):
    bound = logger.bind(module=ctx("PM-API", style="magenta", show_key=True))

    _, kwargs = bound.process("message", {"extra": None})

    assert kwargs["extra"]["context"] == {
        "context::module": ctx("PM-API", style="magenta", show_key=True)
    }


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_bind_process_copies_read_only_extra_mapping(logger):
    bound = logger.bind(module=ctx("PM-API", style="magenta", show_key=True))
    read_only_extra = MappingProxyType(
        {
            "context": {"request_id": ctx("req-42", style="cyan", show_key=True)},
            "user": "alice",
        }
    )

    _, kwargs = bound.process("message", {"extra": read_only_extra})

    assert kwargs["extra"] is not read_only_extra
    assert kwargs["extra"]["user"] == "alice"
    assert kwargs["extra"]["context"] == {
        "context::module": ctx("PM-API", style="magenta", show_key=True),
        "request_id": ctx("req-42", style="cyan", show_key=True),
    }
