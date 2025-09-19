import multiprocessing as mp

import pytest
from rich.panel import Panel
from rich.table import Table

from logurich import ctx
from logurich.core import global_configure, mp_configure


def worker_process(logger_):
    from logurich.core import logger

    mp_configure(logger_)
    logger.debug("Test message from child process")


def worker_with_context(logger_):
    from logurich.core import logger

    mp_configure(logger_)
    logger.info("Message with worker context")


def worker_with_rich_logging(logger_):
    from logurich.core import logger

    mp_configure(logger_)
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
def test_mp_configure(logger, buffer):
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
def test_global_configure_in_mp(logger, buffer):
    with global_configure(worker=ctx("TestWorker")):
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
