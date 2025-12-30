__version__ = "0.4.0"

from .console import (
    console,
    rich_configure_console,
    rich_get_console,
    rich_set_console,
    rich_to_str,
)
from .core import (
    LOG_LEVEL_CHOICES,
    ctx,
    global_configure,
    global_set_context,
    init_logger,
    level_restore,
    level_set,
    logger,
    mp_configure,
    propagate_loguru_to_std_logger,
)

init_logger("INFO")

__all__ = [
    "logger",
    "ctx",
    "init_logger",
    "mp_configure",
    "global_configure",
    "global_set_context",
    "propagate_loguru_to_std_logger",
    "level_restore",
    "level_set",
    "console",
    "rich_configure_console",
    "rich_get_console",
    "rich_set_console",
    "rich_to_str",
    "LOG_LEVEL_CHOICES",
]
