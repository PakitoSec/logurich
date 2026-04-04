"""Click integration module for logurich.

Provides decorators and utilities to seamlessly integrate logurich logging
with Click CLI applications.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, Optional, TypeVar

import click

from . import LOG_LEVEL_CHOICES, init_logger, shutdown_logger

LOGGER_PARAM_NAMES = (
    "logger_level",
    "logger_verbose",
    "logger_filename",
    "logger_level_by_module",
    "logger_rich",
)
_CLICK_SHUTDOWN_META_KEY = "logurich_shutdown_registered"
_logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def click_logger_params(func: F) -> F:
    """Decorator to add logger configuration options to Click commands.

    This decorator automatically adds the following CLI options:
    - ``-l, --logger-level``: Set the logging level (DEBUG, INFO, WARNING, etc.)
    - ``-v, --logger-verbose``: Increase verbosity (can be used multiple times)
    - ``--logger-filename``: Enable file logging with specified filename
    - ``--logger-level-by-module``: Set specific log levels per module
    - ``--logger-rich``: Enable Rich handler for enhanced console output

    The decorator initializes the logger before the command function executes.

    Args:
        func: The Click command function to decorate.

    Returns:
        The decorated function with logger CLI options.

    Example:
        >>> import click
        >>> import logging
        >>> from logurich.opt_click import click_logger_params
        >>> logger = logging.getLogger(__name__)
        >>>
        >>> @click.command()
        >>> @click_logger_params
        >>> def my_cli():
        >>>     logger.info("Application started")
        >>>
        >>> if __name__ == "__main__":
        >>>     my_cli()

    Raises:
        RuntimeError: If logger parameters are missing from the function invocation.
    """

    @click.option(
        "-l",
        "--logger-level",
        default="INFO",
        help="Logger level",
        type=click.Choice(LOG_LEVEL_CHOICES, case_sensitive=False),
    )
    @click.option("-v", "--logger-verbose", help="Logger increase verbose", count=True)
    @click.option(
        "--logger-filename",
        help="Logger log filename",
        type=str,
    )
    @click.option(
        "--logger-level-by-module",
        multiple=True,
        help="Logger level by module",
        type=(str, str),
    )
    @click.option(
        "--logger-rich",
        is_flag=True,
        help="Enable rich handler for enhanced console output",
        type=bool,
        default=False,
    )
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        missing = [name for name in LOGGER_PARAM_NAMES if name not in kwargs]
        if missing:
            raise RuntimeError(
                "Logger CLI parameters missing from invocation: {}".format(
                    ", ".join(missing)
                )
            )
        logger_kwargs = {name: kwargs.pop(name) for name in LOGGER_PARAM_NAMES}
        click_logger_init(**logger_kwargs)
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def click_logger_init(
    logger_level: str,
    logger_verbose: int,
    logger_filename: Optional[str],
    logger_level_by_module: tuple[tuple[str, str], ...],
    logger_rich: bool,
) -> None:
    """Initialize the logger with parameters from Click CLI options.

    This function is called internally by the click_logger_params decorator
    to configure the logger based on CLI arguments.

    Args:
        logger_level: The minimum logging level (e.g., "DEBUG", "INFO").
        logger_verbose: Verbosity level (0-3).
        logger_filename: Path to log file, or None for console-only logging.
        logger_level_by_module: Tuple of (module_name, level) pairs for per-module levels.
        logger_rich: Whether to use Rich handler for enhanced console output.

    Example:
        This function is typically not called directly. It's invoked by the
        click_logger_params decorator.
    """
    lbm = {}
    for mod, level in logger_level_by_module:
        lbm[mod] = level
    log_path = init_logger(
        logger_level,
        logger_verbose,
        log_filename=logger_filename,
        level_by_module=lbm,
        rich_handler=logger_rich,
    )
    click_ctx = click.get_current_context(silent=True)
    if click_ctx is not None and not click_ctx.meta.get(_CLICK_SHUTDOWN_META_KEY):
        click_ctx.call_on_close(shutdown_logger)
        click_ctx.meta[_CLICK_SHUTDOWN_META_KEY] = True
    _logger.debug("Log level:            %s", logger_level)
    _logger.debug("Log verbose:          %s", logger_verbose)
    _logger.debug("Log filename:         %s", logger_filename)
    _logger.debug("Log path:             %s", log_path)
    _logger.debug("Log level by module:  %s", lbm)
    _logger.debug("Log rich handler:     %s", logger_rich)
