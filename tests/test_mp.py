import multiprocessing as mp

import pytest
from rich.panel import Panel
from rich.table import Table

from logurich import global_context_configure


def worker_process(logger_):
    from logurich.core import logger

    logger.configure_child_logger(logger_)
    logger.debug("Test message from child process")


def worker_with_context(logger_):
    from logurich.core import logger

    logger.configure_child_logger(logger_)
    logger.info("Message with worker context")


def worker_process_context(logger_):
    from logurich import logger

    logger.configure_child_logger(logger_)
    with logger.contextualize(task_id=logger.ctx("task-id")):
        logger.info("Message with context")


def worker_with_rich_logging(logger_):
    from logurich.core import logger

    logger.configure_child_logger(logger_)
    panel = Panel("Test rich panel")
    table = Table(title="Test table")
    table.add_column("Column 1")
    table.add_column("Column 2")
    table.add_row("Value 1", "Value 2")
    logger.rich("INFO", panel, table, title="Rich Test")


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_configure_child_logger(logger, buffer):
    process = mp.Process(target=worker_process, args=(logger,))
    process.start()
    process.join()
    logger.complete()
    assert any(
        "Test message from child process" in log
        for log in buffer.getvalue().splitlines()
    )


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_configure_child_logger_context(logger, buffer):
    process = mp.Process(target=worker_process_context, args=(logger,))
    process.start()
    process.join()
    logger.complete()
    assert any("task-id" in log for log in buffer.getvalue().splitlines())


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_global_configure_in_mp(logger, buffer):
    with global_context_configure(worker=logger.ctx("TestWorker")):
        process = mp.Process(target=worker_with_context, args=(logger,))
        process.start()
        process.join()
    logger.complete()
    assert "TestWorker" in buffer.getvalue()


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": True}],
    indirect=True,
)
def test_rich_logging_in_mp(logger, buffer):
    process = mp.Process(target=worker_with_rich_logging, args=(logger,))
    process.start()
    process.join()
    logger.complete()
    assert "Column 1" in buffer.getvalue()
    assert "Column 2" in buffer.getvalue()
    assert "Value 1" in buffer.getvalue()
    assert "Value 2" in buffer.getvalue()
    assert "Rich Test" in buffer.getvalue()
