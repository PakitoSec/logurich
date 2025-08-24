# logurich

A Python library combining Loguru and Rich for beautiful logging.

## Installation

```bash
pip install logurich
```

## Usage

Logurich now supports direct imports from the package root, making it easier to access the logger and console:

```python
# Import directly from the package root
from logurich import logger, console

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
```
