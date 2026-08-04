"""Small dependency-free Logurich performance smoke benchmark."""

from __future__ import annotations

import gc
import logging
import time
from io import StringIO
from typing import Callable

from rich.panel import Panel
from rich.table import Table

from logurich import get_logger, init_logger, shutdown_logger
from logurich.console import rich_configure_console


def measure(label: str, operation: Callable[[], None], iterations: int) -> None:
    gc.collect()
    start = time.perf_counter()
    for _ in range(iterations):
        operation()
    elapsed = time.perf_counter() - start
    print(f"{label:<30} {elapsed / iterations * 1_000_000:>10.2f} us/call")


def main() -> None:
    output = StringIO()
    rich_configure_console(file=output, width=120)
    init_logger("DEBUG", enqueue=False)
    logger = get_logger("benchmark")

    logger.setLevel(logging.INFO)
    measure("filtered DEBUG", lambda: logger.debug("filtered"), 20_000)
    measure("plain INFO", lambda: logger.info("emitted %s", 1), 2_000)
    measure(
        "INFO with context",
        lambda: logger.info("emitted", request_id="req-42", duration_ms=12),
        2_000,
    )

    panel = Panel("ready")
    table = Table()
    table.add_column("metric")
    table.add_row("42")
    measure("Panel and Table", lambda: logger.rich("INFO", panel, table), 200)

    def log_exception() -> None:
        try:
            raise ValueError("benchmark")
        except ValueError:
            logger.exception("failed")

    measure("plain exception", log_exception, 100)
    shutdown_logger()

    output.seek(0)
    output.truncate(0)
    init_logger("INFO", console="rich", enqueue=False)
    measure("Rich exception", log_exception, 100)
    shutdown_logger()

    output.seek(0)
    output.truncate(0)
    init_logger("INFO", enqueue=True)
    queued = get_logger("benchmark.queue")
    measure("queued INFO submission", lambda: queued.info("queued"), 2_000)
    shutdown_logger()


if __name__ == "__main__":
    main()
