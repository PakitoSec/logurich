"""Public package exports for logurich."""

__version__ = "0.8.0"

from .console import (
    console,
    rich_configure_console,
    rich_get_console,
    rich_set_console,
    rich_to_str,
)
from .core import (
    LOG_LEVEL_CHOICES,
    BoundLogger,
    ContextValue,
    LogLevel,
    LogurichLogger,
    configure_child_logging,
    ctx,
    get_log_queue,
    global_context_configure,
    global_context_set,
    init_logger,
    logger,
    shutdown_logger,
)

__all__ = [
    "init_logger",
    "logger",
    "get_log_queue",
    "configure_child_logging",
    "shutdown_logger",
    "ctx",
    "ContextValue",
    "BoundLogger",
    "LogurichLogger",
    "global_context_configure",
    "global_context_set",
    "console",
    "rich_configure_console",
    "rich_get_console",
    "rich_set_console",
    "rich_to_str",
    "LOG_LEVEL_CHOICES",
    "LogLevel",
]
