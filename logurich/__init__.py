__version__ = "0.4.0"

from .console import configure_console, console, get_console, rich_to_str, set_console
from .core import (
    LOG_LEVEL_CHOICES,
    ContextValue,
    ctx,
    global_configure,
    global_set_context,
    init_logger,
    logger,
    mp_configure,
    propagate_loguru_to_std_logger,
    restore_level,
    set_level,
)

init_logger("INFO")

__all__ = [
    "logger",
    "init_logger",
    "mp_configure",
    "global_configure",
    "global_set_context",
    "ContextValue",
    "ctx",
    "LOG_LEVEL_CHOICES",
    "propagate_loguru_to_std_logger",
    "restore_level",
    "set_level",
    "configure_console",
    "console",
    "get_console",
    "set_console",
    "rich_to_str",
]
