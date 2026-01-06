"""Public package exports for logurich."""

__version__ = "0.7.1"

from .console import (
    console,
    rich_configure_console,
    rich_get_console,
    rich_set_console,
    rich_to_str,
)
from .core import (
    LOG_LEVEL_CHOICES,
    LogLevel,
    LoguRich,
    ctx,
    global_context_configure,
    global_context_set,
    init_logger,
    logger,
    propagate_loguru_to_std_logger,
)

__all__ = [
    "init_logger",
    "logger",
    "ctx",
    "global_context_configure",
    "global_context_set",
    "propagate_loguru_to_std_logger",
    "console",
    "rich_configure_console",
    "rich_get_console",
    "rich_set_console",
    "rich_to_str",
    "LOG_LEVEL_CHOICES",
    "LogLevel",
    "LoguRich",
]
