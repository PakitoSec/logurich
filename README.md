# logurich

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/logurich.svg)](https://pypi.org/project/logurich/)

A Python library combining standard logging and Rich for beautiful logging.

## Installation

```bash
pip install logurich
pip install logurich[click]
```

## Usage

```python
from rich.panel import Panel

from logurich import global_context_configure, init_logger, logger, shutdown_logger

init_logger("INFO", enqueue=False)

logger.info("This is a log message")
logger.info("Hello %s", "world")

logger.info(
    "Rich renderables",
    extra={
        "renderables": (
            Panel("Rich panel output", border_style="green"),
        )
    },
)

with global_context_configure(app=logger.ctx("demo", style="yellow")):
    logger.info("This log has scoped context")

logger.info(
    "Per-call context",
    extra={
        "context": {
            "session": logger.ctx("sess-42", style="cyan", show_key=True),
        }
    },
)

shutdown_logger()
```

`logger.ctx(...)` is shorthand for the existing module-level `ctx(...)` helper. The module-level helper remains supported if you prefer `extra={"context": {"key": ctx(...)}}`.

## Using Logurich in Reusable Libraries

If you are writing a Python library that will be imported by another program, the library should not call `init_logger()` on its own. Let the main application own logging configuration, handler setup, and shutdown.

Inside the library, use standard named loggers:

```python
# mylib/service.py
import logging

from rich.panel import Panel

from logurich import ctx

logger = logging.getLogger(__name__)


def run_job(job_id: str) -> None:
    logger.info(
        "Starting job %s",
        job_id,
        extra={"context": {"job": ctx(job_id, style="cyan", show_key=True)}},
    )
    logger.info(
        "Job details",
        extra={
            "renderables": (
                Panel(f"Job {job_id} is running", border_style="green"),
            )
        },
    )
```

Then configure Logurich once in the main program:

```python
# main.py
from logurich import init_logger, shutdown_logger
from mylib.service import run_job

init_logger("INFO", enqueue=False)

run_job("job-42")

shutdown_logger()
```

Guidelines for libraries:

- Use `logging.getLogger(__name__)` inside library modules.
- Do not call `init_logger()` or `shutdown_logger()` from library code.
- Emit normal stdlib log calls such as `logger.info("Value %s", value)`.
- Use `extra={"context": ...}` and `extra={"renderables": ...}` only as optional metadata; they render nicely when the consuming application uses Logurich, and `logger.ctx(...)` / `logger.rich(...)` are also available when Logurich has been imported/configured by the application.
- If the library starts worker processes and the application uses `enqueue=True`, accept the queue from the application and call `configure_child_logging(queue)` inside each worker process.

## Multiprocessing

When `enqueue=True`, Logurich is process-safe only if worker processes send records through the shared logging queue created by the parent process.

```python
import logging
import multiprocessing as mp

from logurich import configure_child_logging, get_log_queue, init_logger, shutdown_logger


def worker(log_queue: mp.Queue, worker_id: int) -> None:
    configure_child_logging(log_queue)
    logging.getLogger(f"worker.{worker_id}").info("worker=%s ready", worker_id)


def main() -> None:
    init_logger("INFO", enqueue=True)
    log_queue = get_log_queue()

    processes = [
        mp.Process(target=worker, args=(log_queue, index), name=f"worker-{index}")
        for index in range(3)
    ]

    for process in processes:
        process.start()

    for process in processes:
        process.join()

    shutdown_logger()
```

Only the process that calls `init_logger(..., enqueue=True)` owns the console and file handlers. Child processes must call `configure_child_logging(queue)` before logging.

## Click CLI helper

Install the optional Click extra to automatically expose logger configuration flags inside your commands:

```python
import click
from logurich import logger
from logurich.opt_click import click_logger_params


@click.command()
@click_logger_params
def cli():
    logger.info("Click integration ready!")
```

The `click_logger_params` decorator injects `--logger-level`, `--logger-verbose`, `--logger-filename`, `--logger-level-by-module`, and `--logger-rich` flags and configures Logurich before your command logic runs. The usage example above is also available at `examples/click_cli.py`.
