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

from logurich import get_logger, init_logger

init_logger("INFO", enqueue=False)

logger = get_logger(__name__)

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

with logger.contextualize(app=logger.ctx("demo", style="yellow")):
    logger.info("This log has scoped context")

logger.info(
    "Per-call context",
    extra={
        "context": {
            "session": logger.ctx("sess-42", style="cyan", show_key=True),
        }
    },
)

```

For full IDE autocompletion of `ctx(...)`, `rich(...)`, `bind(...)`, and `contextualize(...)`, use `get_logger(...)` from logurich instead of `logging.getLogger(...)`. It returns the same logger instance but typed as `LogurichLogger`. `logger.ctx(...)` is shorthand for the existing module-level `ctx(...)` helper, and `logger.contextualize(...)` is a convenience alias for `global_context_configure(...)`. The module-level helpers remain supported if you prefer `global_context_configure(...)` or `extra={"context": {"key": ctx(...)}}`.

`logging.getLogger(...)` still works at runtime — only the typing differs.

For short-lived scripts and CLIs, `init_logger()` automatically registers an `atexit` hook, so you do not need to call `shutdown_logger()` just to flush logs at process exit.

## Named Loggers

Use the standard library to create named loggers:

```python
from logurich import get_logger, init_logger

init_logger("INFO", enqueue=False)

logger = get_logger(__name__)
logger.info("Hello from %s", __name__)
```

Use `get_logger(...)` from logurich for typed access. `logging.getLogger(...)` still works at runtime.

## Using Logurich in Reusable Libraries

If you are writing a Python library that will be imported by another program, the library should not call `init_logger()` on its own. Let the main application own logging configuration, handler setup, and shutdown.

Inside the library, use standard named loggers:

```python
# mylib/service.py
from rich.panel import Panel

from logurich import ctx, get_logger

logger = get_logger(__name__)


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
from logurich import init_logger
from mylib.service import run_job

init_logger("INFO", enqueue=False)

run_job("job-42")
```

Guidelines for libraries:

- Use `get_logger(__name__)` from logurich inside library modules.
- Do not call `init_logger()` or `shutdown_logger()` from library code.
- Emit normal stdlib log calls such as `logger.info("Value %s", value)`.
- Use `extra={"context": ...}` and `extra={"renderables": ...}` only as optional metadata; they render nicely when the consuming application uses Logurich, and `logger.ctx(...)` / `logger.rich(...)` are also available when Logurich has been imported/configured by the application.
- If the library starts worker processes and the application uses `enqueue=True`, accept the queue from the application and call `configure_child_logging(queue)` inside each worker process.

## Multiprocessing

When `enqueue=True`, Logurich is process-safe only if worker processes send records through the shared logging queue created by the parent process.

```python
import multiprocessing as mp

from logurich import configure_child_logging, get_log_queue, get_logger, init_logger


def worker(log_queue: mp.Queue, worker_id: int) -> None:
    configure_child_logging(log_queue)
    get_logger(f"worker.{worker_id}").info("worker=%s ready", worker_id)


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

```

Only the process that calls `init_logger(..., enqueue=True)` owns the console and file handlers. Child processes must call `configure_child_logging(queue)` before logging.

Call `shutdown_logger()` explicitly only when you need deterministic teardown before process exit, such as in tests or when reconfiguring logging multiple times in the same interpreter.

## Click CLI helper

Install the optional Click extra to automatically expose logger configuration flags inside your commands:

```python
import click

from logurich import get_logger
from logurich.opt_click import click_logger_params


@click.command()
@click_logger_params
def cli():
    logger = get_logger(__name__)
    logger.info("Click integration ready!")
```

The `click_logger_params` decorator injects `--logger-level`, `--logger-verbose`, `--logger-filename`, `--logger-level-by-module`, and `--logger-rich` flags and configures Logurich before your command logic runs. The usage example above is also available at `examples/click_cli.py`.

## Idempotent initialisation (`force`)

By default, calling `init_logger()` a second time is a no-op — the existing configuration is kept and the call returns `None`. Pass `force=True` to tear down the current setup and reconfigure from scratch:

```python
from logurich import init_logger

init_logger("INFO", enqueue=False)          # first call: configures logging
init_logger("DEBUG", enqueue=False)         # no-op, returns None
init_logger("DEBUG", enqueue=False, force=True)  # reconfigures logging
```

This is useful when tests or interactive sessions need to reset logging between runs.

## User input

The `user_input` module provides Rich-enhanced prompts with type coercion, hidden input, and optional timeouts. It does **not** depend on Click.

```python
from logurich import get_logger, init_logger, user_input, user_input_with_timeout

init_logger("INFO", enqueue=False)
logger = get_logger(__name__)

# Basic string input
name = user_input("Enter your name", type=str)

# Integer input with a default value
count = user_input("How many items?", type=int, default=5)

# Hidden input (e.g. passwords)
secret = user_input("Enter secret", type=str, hide_input=True)

# Input with a timeout (5 seconds, Unix only — falls back to regular input on Windows)
answer = user_input_with_timeout("Quick! Type something", timeout_duration=5)
```

A runnable example is available at `examples/user_input_example.py`.
