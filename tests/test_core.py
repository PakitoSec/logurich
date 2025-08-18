import pytest

from logurich.core import global_configure, global_set_context


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
    with global_configure(context__y_exec_id="id_123"):
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
    global_set_context(context__y_exec_id="id_123")
    logger.info("Hello, world!")
    logger.debug("Debug, world!")
    logger.complete()
    assert all("id_123" in log for log in buffer.getvalue().splitlines())
