import json

import pytest

from logurich import ctx, global_configure, global_set_context, init_logger


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
    with global_configure(exec_id=ctx("id_123", style="yellow")):
        logger.info("Hello, world!")
        logger.debug("Debug, world!")
        logger.complete()
        assert all("id_123" in log for log in buffer.getvalue().splitlines())


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_set_context(logger, buffer):
    global_set_context(exec_id=ctx("id_123", style="yellow"))
    logger.info("Hello, world!")
    logger.debug("Debug, world!")
    logger.complete()
    assert all("id_123" in log for log in buffer.getvalue().splitlines())
    global_set_context(exec_id=None)


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
