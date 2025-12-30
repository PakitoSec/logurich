import json

import pytest

from logurich import (
    global_context_configure,
    global_context_set,
    init_logger,
)


@pytest.mark.parametrize(
    "logger",
    [{"level": "INFO", "enqueue": False}, {"level": "INFO", "enqueue": True}],
    indirect=True,
)
def test_level_info(logger, buffer):
    logger.info("Hello, world!")
    logger.debug("Debug, world!")
    logger.complete()
    assert "Hello, world!" in buffer.getvalue()
    assert "Debug, world" not in buffer.getvalue()


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_level_debug(logger, buffer):
    logger.info("Hello, world!")
    logger.debug("Debug, world!")
    logger.complete()
    assert "Hello, world!" in buffer.getvalue().splitlines()[0]
    assert "Debug, world" in buffer.getvalue().splitlines()[1]


@pytest.mark.parametrize(
    "logger",
    [
        {"level": "DEBUG", "enqueue": False, "verbose": 3},
        {"level": "DEBUG", "enqueue": True, "verbose": 3},
    ],
    indirect=True,
)
def test_level_debug_verbose(logger, buffer):
    logger.info("Hello, world!")
    logger.debug("Debug, world!")
    logger.complete()
    assert "Hello, world!" in buffer.getvalue().splitlines()[0]
    assert "Debug, world" in buffer.getvalue().splitlines()[1]


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_global_configure(logger, buffer):
    with global_context_configure(exec_id=logger.ctx("id_123", style="yellow")):
        logger.info("Hello, world!")
        logger.debug("Debug, world!")
        logger.complete()
        assert all("id_123" in log for log in buffer.getvalue().splitlines())


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_global_configure_restores_previous(logger, buffer):
    with global_context_configure(exec_id=logger.ctx("outer_ctx", style="yellow")):
        logger.info("outer message")
        with global_context_configure(exec_id=logger.ctx("inner_ctx", style="cyan")):
            logger.info("inner message")
        logger.info("outer message again")
    logger.info("plain message")
    logger.complete()
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
def test_with_configure(logger, buffer):
    with logger.contextualize(exec_id=logger.ctx("task-id", style="yellow")):
        logger.info("Hello, world!")
        logger.debug("Debug, world!")
    logger.complete()
    assert all("task-id" in log for log in buffer.getvalue().splitlines())


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_set_context(logger, buffer):
    global_context_set(exec_id=logger.ctx("id_123", style="yellow"))
    logger.info("Hello, world!")
    logger.debug("Debug, world!")
    logger.complete()
    assert all("id_123" in log for log in buffer.getvalue().splitlines())
    global_context_set(exec_id=None)


@pytest.mark.parametrize(
    "level, enqueue",
    [
        ("DEBUG", False),
        ("DEBUG", True),
    ],
)
def test_loguru_serialize_env(monkeypatch, logger, level, enqueue, buffer):
    monkeypatch.setenv("LOGURU_SERIALIZE", "1")
    init_logger(level, enqueue=enqueue)
    logger.info("Serialized {}", "output")
    logger.complete()
    log_lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    assert log_lines, "No serialized output captured"
    payload = json.loads(log_lines[0])
    assert payload["record"]["message"] == "Serialized output"


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}],
    indirect=True,
)
def test_logger_ctx_in_bind(logger, buffer):
    """logger.ctx() should work seamlessly with logger.bind()."""
    logger.bind(session=logger.ctx("sess-42", style="cyan")).info("bound message")
    logger.complete()
    assert "sess-42" in buffer.getvalue()


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}],
    indirect=True,
)
def test_set_level_filters_messages(logger, buffer):
    """level_set() should temporarily raise the minimum log level."""
    logger.debug("before level_set")
    logger.level_set("WARNING")
    logger.debug("should be filtered")
    logger.info("also filtered")
    logger.warning("should appear")
    logger.complete()
    output = buffer.getvalue()
    assert "before level_set" in output
    assert "should be filtered" not in output
    assert "also filtered" not in output
    assert "should appear" in output


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}],
    indirect=True,
)
def test_restore_level_resets_filtering(logger, buffer):
    """level_restore() should reset the log level to the original."""
    logger.level_set("ERROR")
    logger.warning("filtered warning")
    logger.level_restore()
    logger.debug("after restore")
    logger.complete()
    output = buffer.getvalue()
    assert "filtered warning" not in output
    assert "after restore" in output
