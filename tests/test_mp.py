import logging
import multiprocessing as mp

from rich.panel import Panel
from rich.table import Table

from logurich import (
    configure_child_logging,
    ctx,
    get_log_queue,
    global_context_configure,
    init_logger,
    shutdown_logger,
)


def worker_process(queue):
    configure_child_logging(queue)
    logging.getLogger("workers.basic").info("Test message from child process")


def worker_process_context(queue):
    configure_child_logging(queue)
    with global_context_configure(task_id=ctx("task-id", show_key=True)):
        logging.getLogger("workers.context").info("Message with context")


def worker_with_rich_logging(queue):
    configure_child_logging(queue)
    panel = Panel("Test rich panel")
    table = Table(title="Test table")
    table.add_column("Column 1")
    table.add_column("Column 2")
    table.add_row("Value 1", "Value 2")
    logging.getLogger("workers.rich").info(
        "Rich Test",
        extra={"renderables": (panel, table)},
    )


def test_configure_child_logging_routes_records_to_parent(buffer):
    init_logger("DEBUG", enqueue=True)
    log_queue = get_log_queue()

    process = mp.Process(target=worker_process, args=(log_queue,))
    process.start()
    process.join()
    assert process.exitcode == 0

    logging.getLogger("parent").info("Parent message")
    shutdown_logger()

    output = buffer.getvalue()
    assert "Test message from child process" in output
    assert "Parent message" in output


def test_child_process_context_is_rendered(buffer):
    init_logger("DEBUG", enqueue=True)
    log_queue = get_log_queue()

    process = mp.Process(target=worker_process_context, args=(log_queue,))
    process.start()
    process.join()
    assert process.exitcode == 0

    shutdown_logger()
    assert "task_id=task-id" in buffer.getvalue()


def test_rich_logging_in_child_process(buffer):
    init_logger("DEBUG", enqueue=True)
    log_queue = get_log_queue()

    process = mp.Process(target=worker_with_rich_logging, args=(log_queue,))
    process.start()
    process.join()
    assert process.exitcode == 0

    shutdown_logger()
    output = buffer.getvalue()
    assert "Column 1" in output
    assert "Column 2" in output
    assert "Value 1" in output
    assert "Value 2" in output
    assert "Rich Test" in output
