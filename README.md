# logurich

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/logurich.svg)](https://pypi.org/project/logurich/)


A Python library combining Loguru and Rich for beautiful logging.

## Installation

```bash
pip install logurich
pip install logurich[click]
```

## Usage

```python
from logurich import logger

# Use the logger
logger.info("This is a log message")

# Use rich color and rich object formatting
logger.info("[bold green]Rich formatted text[/bold green]")

# Panel rich object with logger and prefix
logger.rich(
    "INFO", Panel("Rich Panel", border_style="green"), title="Rich Panel Object"
)

# Panel rich object without prefix
logger.rich(
    "INFO",
    Panel("Rich Panel without prefix", border_style="green"),
    title="Rich Panel",
    prefix=False,
)

# Temporarily raise the minimum level
logger.level_set("WARNING")
logger.info("filtered")
logger.warning("visible")
logger.level_restore()
```

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

The `click_logger_params` decorator injects `--logger-level`, `--logger-verbose`, `--logger-filename`, `--logger-level-by-module`, and `--logger-diagnose` flags and configures Logurich before your command logic runs. The usage example above is also available at `examples/click_cli.py`.
