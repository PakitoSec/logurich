"""Public package exports for logurich."""

__version__ = "1.0.0"

from .console import (
    console,
    reset_console_after_fork,
    rich_configure_console,
    rich_get_console,
    rich_set_console,
    rich_to_str,
)
from .context import (
    ContextValue,
    ctx,
    global_clear_context,
    global_context,
    global_context_set,
    global_context_unset,
)
from .core import (
    CONSOLE_MODE_CHOICES,
    FILE_MODE_CHOICES,
    LOG_LEVEL_CHOICES,
    ConsoleMode,
    FileMode,
    LogLevel,
    LogLevels,
    LogurichLogger,
    configure_child_logging,
    get_log_levels,
    get_log_queue,
    get_logger,
    init_logger,
    shutdown_logger,
)
from .premarkup import (
    MAX_PREMARKUP_INPUT,
    PremarkupAction,
    premarkup_actions,
    process_premarkup,
    process_premarkup_to_text,
    register_premarkup,
    unregister_premarkup,
)
from .serialize import SCHEMA_VERSION, serialize_renderables
from .user_input import timeout, user_input, user_input_with_timeout

__all__ = [
    "init_logger",
    "get_log_queue",
    "get_log_levels",
    "configure_child_logging",
    "shutdown_logger",
    "ctx",
    "ContextValue",
    "LogurichLogger",
    "global_context",
    "global_context_set",
    "global_context_unset",
    "global_clear_context",
    "console",
    "reset_console_after_fork",
    "rich_configure_console",
    "rich_get_console",
    "rich_set_console",
    "rich_to_str",
    "LOG_LEVEL_CHOICES",
    "CONSOLE_MODE_CHOICES",
    "FILE_MODE_CHOICES",
    "LogLevel",
    "LogLevels",
    "ConsoleMode",
    "FileMode",
    "get_logger",
    "timeout",
    "user_input",
    "user_input_with_timeout",
    "SCHEMA_VERSION",
    "serialize_renderables",
    "MAX_PREMARKUP_INPUT",
    "PremarkupAction",
    "premarkup_actions",
    "process_premarkup",
    "process_premarkup_to_text",
    "register_premarkup",
    "unregister_premarkup",
]
