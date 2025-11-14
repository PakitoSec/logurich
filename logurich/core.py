from __future__ import annotations

import contextlib
import logging
import os
import sys
import time
from dataclasses import dataclass
from functools import partialmethod, wraps
from typing import Any, Literal, Union, get_args

from loguru import logger as _logger
from loguru._logger import Logger as _Logger
from rich.console import ConsoleRenderable
from rich.text import Text
from rich.traceback import Traceback

from .console import rich_console_renderer, rich_to_str
from .handler import CustomHandler, CustomRichHandler
from .struct import extra_logger


def rich_logger(
    self: _Logger,
    log_level: str,
    *renderables: Union[ConsoleRenderable, str],
    title: str = "",
    prefix: bool = True,
    end: str = "\n",
):
    self.opt(depth=1).bind(rich_console=renderables, rich_format=prefix, end=end).log(
        log_level, title
    )


_Logger.rich = partialmethod(rich_logger)
logger = _logger


COLOR_ALIASES = {
    "g": "green",
    "e": "blue",
    "c": "cyan",
    "m": "magenta",
    "r": "red",
    "w": "white",
    "y": "yellow",
    "b": "bold",
    "u": "u",
    "bg": " on ",
}


def _normalize_style(style: str | None) -> str | None:
    if style is None:
        return None
    style = style.strip()
    if not style:
        return None
    return COLOR_ALIASES.get(style, style)


def _wrap_markup(style: str | None, text: str) -> str:
    normalized = _normalize_style(style)
    if not normalized:
        return text
    return f"[{normalized}]{text}[/{normalized}]"


def _context_display_name(name: str) -> str:
    if name.startswith("context::"):
        return name.split("::", 1)[1]
    return name


@dataclass(frozen=True)
class ContextValue:
    value: Any
    value_style: str | None = None
    bracket_style: str | None = None
    label: str | None = None
    show_key: bool = False

    def _label(self, key: str) -> str | None:
        if self.label is not None:
            return self.label
        if self.show_key:
            return key
        return None

    def render(self, key: str, *, is_rich_handler: bool) -> str:
        label = self._label(key)
        value_text = str(self.value)
        value_text = _wrap_markup(self.value_style, value_text)
        if label:
            body = f"{label}={value_text}"
        else:
            body = value_text
        if is_rich_handler:
            return body
        left = _wrap_markup(self.bracket_style, "[")
        right = _wrap_markup(self.bracket_style, "]")
        if not left:
            left = "["
        if not right:
            right = "]"
        return f"{left}{body}{right}"


def ctx(
    value: Any,
    *,
    style: str | None = None,
    value_style: str | None = None,
    bracket_style: str | None = None,
    label: str | None = None,
    show_key: bool | None = None,
) -> ContextValue:
    """Build a ContextValue helper for structured context logging."""

    effective_value_style = value_style if value_style is not None else style
    return ContextValue(
        value=value,
        value_style=effective_value_style,
        bracket_style=bracket_style,
        label=label,
        show_key=bool(show_key) if show_key is not None else False,
    )


def _logger_add_ctx_timestamp(kwargs: dict, stack: bool = True):
    new_kwargs = {}
    for k in list(kwargs.keys()):
        if k.startswith("context") and stack is True and "#" not in k:
            v = kwargs.pop(k)
            new_k = k + "#" + str(time.time_ns())
            new_kwargs[new_k] = v
    kwargs.update(new_kwargs)


def logger_patch(record):
    context = {}
    for name in record["extra"]:
        if name.startswith("context") is False:
            continue
        splitted_name = name.split("#")
        if len(splitted_name) == 2:
            real_name, timer = splitted_name
        else:
            real_name, timer = name, 0
        context[name] = real_name, float(timer)
    sorted_context_name = sorted(context, key=lambda d: context[d][1])
    for name in sorted_context_name:
        value = record["extra"].pop(name)
        real_name, _ = context[name]
        record["extra"][real_name] = value


def logger_bind(args, kwargs):
    _logger_add_ctx_timestamp(kwargs, stack=False)


def logger_ctx(args, kwargs):
    _ = kwargs.get("stack", False)
    _logger_add_ctx_timestamp(kwargs, stack=False)


@contextlib.contextmanager
def global_configure(**kwargs):
    global_set_context(**kwargs)
    try:
        yield
    finally:
        global_set_context(**{k: None for k in kwargs})


def _normalize_context_key(key: str) -> str:
    if key.startswith("context::"):
        return key
    if key.startswith("context"):
        raise ValueError(
            "Legacy context keys using the 'context__' pattern are no longer supported."
        )
    return f"context::{key}"


def _coerce_context_value(value: Any) -> ContextValue | None:
    if value is None:
        return None
    if isinstance(value, ContextValue):
        return value
    return ContextValue(value=value)


def global_set_context(**kwargs):
    for key, value in kwargs.items():
        normalized_key = _normalize_context_key(key)
        normalized_value = _coerce_context_value(value)

        matching_keys = [
            existing
            for existing in list(extra_logger.keys())
            if existing == normalized_key or existing.startswith(normalized_key + "#")
        ]
        for existing in matching_keys:
            extra_logger.pop(existing, None)

        if normalized_value is None:
            continue

        extra_logger[normalized_key] = normalized_value

    logger.configure(extra=extra_logger)


def logger_wraps(*, entry=True, exit=True, level="DEBUG"):
    def wrapper(func):
        name = func.__name__

        @wraps(func)
        def wrapped(*args, **kwargs):
            logger_ = logger.opt(depth=1)
            if entry:
                logger_.log(
                    level, "Entering '{}' (args={}, kwargs={})", name, args, kwargs
                )
            result = func(*args, **kwargs)
            if exit:
                logger_.log(level, "Exiting '{}' (result={})", name, result)
            return result

        return wrapped

    return wrapper


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


class Formatter:
    ALL_PADDING_FMT = [
        (0, ""),
        (10, "{process.name}"),
        (22, "{process.name}.{name}:{line}"),
        (25, "{process.name}.{thread.name}.{name}:{line}"),
    ]
    ALL_FMT = [
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | <level>{level: <8}</level> | ",
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | <level>{level: <8}</level> | {process.name}{extra[_padding]} | ",
        (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "<level>{level: <8}</level> | "
            "{process.name}.[magenta]{name}[/magenta]:[blue]{line}[/blue]{extra[_padding]} | "
        ),
        (
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "<level>{level: <8}</level> | "
            "{process.name}.{thread.name}.[cyan]{name}[/cyan]:[blue]{line}[/blue]{extra[_padding]} | "
        ),
    ]
    FMT_RICH = ""
    LEVEL_COLOR_MAP = {
        "TRACE": "dim blue",
        "DEBUG": "bold blue",
        "INFO": "bold",
        "SUCCESS": "bold green",
        "WARNING": "bold yellow",
        "ERROR": "bold red",
        "CRITICAL": "bold white on red",
    }

    def __init__(self, log_level, verbose: int, is_rich_handler: bool = False):
        self.serialize = os.environ.get("LOGURU_SERIALIZE")
        self.is_rich_handler = is_rich_handler
        if self.is_rich_handler is True:
            self._padding = 0
            self.fmt_format = "{process.name}.{name}:{line}"
            self.prefix = Formatter.FMT_RICH
        else:
            self._padding, self.fmt_format = Formatter.ALL_PADDING_FMT[verbose]
            self.prefix = self.ALL_FMT[verbose]
        self.verbose = verbose
        self.log_level = log_level
        self.extra_from_envs = {}
        for name, value in os.environ.items():
            if name.startswith("LOGURU_EXTRA_"):
                key = name.replace("LOGURU_EXTRA_", "")
                self.extra_from_envs[key] = value

    @staticmethod
    def build_context(record: dict, is_rich_handler: bool = False) -> list[str]:
        extra_exist = []
        for name, value in record["extra"].items():
            if not isinstance(value, ContextValue):
                continue
            display_name = _context_display_name(name)
            extra_exist.append(
                value.render(display_name, is_rich_handler=is_rich_handler)
            )
        return extra_exist

    def add_rich_tb(self, record: dict):
        exception = record.get("exception")
        if exception is None:
            return
        exc_type = exception.type
        exc_value = exception.value
        exc_traceback = exception.traceback
        if exc_type and exc_value:
            rich_traceback = Traceback.from_exception(
                exc_type,
                exc_value,
                exc_traceback,
                width=None,
                extra_lines=3,
                theme=None,
                word_wrap=True,
                show_locals=True,
                locals_max_length=10,
                locals_max_string=80,
            )
            record["extra"]["rich_traceback"] = rich_traceback

    def init_record(self, record: dict):
        length = len(self.fmt_format.format(**record))
        self._padding = min(max(self._padding, length), 50)
        list_context = Formatter.build_context(
            record, is_rich_handler=self.is_rich_handler
        )
        record["extra"]["_build_list_context"] = list_context
        record["extra"]["_padding"] = " " * (self._padding - length)
        record["extra"].update(self.extra_from_envs)
        lvl_color = Formatter.LEVEL_COLOR_MAP.get(record["level"].name, "cyan")
        prefix = self.prefix.format(**record)
        prefix = prefix.replace("<level>", f"[{lvl_color}]")
        prefix = prefix.replace("</level>", f"[/{lvl_color}]")
        record["extra"]["_prefix"] = prefix

    def format_file(self, record: dict):
        self.init_record(record)
        end = record["extra"].get("end", "\n")
        prefix = str(Text.from_markup(record["extra"].pop("_prefix")))
        rich_console = record["extra"].pop("rich_console", [])
        list_context = record["extra"].pop("_build_list_context", [])
        record["message"] = str(Text.from_markup(record["message"]))
        rich_data = ""
        if rich_console:
            renderables = rich_console_renderer(
                prefix, record["extra"].get("rich_format", True), rich_console
            )
            rich_data = str(rich_to_str(*renderables, ansi=False))
            rich_data = rich_data.replace("{", " {{").replace("}", "}}")
            record["message"] += "\n" + rich_data
        context = str(
            Text.from_markup("".join(list_context) + " " if list_context else "")
        )
        msg = prefix + context + "{message}" + "{exception}" + end
        return str(msg)

    def format(self, record: dict):
        if self.is_rich_handler:
            self.add_rich_tb(record)
        if self.serialize:
            return self.format_file(record)
        else:
            self.init_record(record)
        return "{message}{exception}"


def set_level(level: str):
    extra_logger.update({"__level_upper_only": level})
    logger.configure(extra=extra_logger)


def restore_level():
    extra_logger.update({"__level_upper_only": None})
    logger.configure(extra=extra_logger)


def filter_records(record):
    min_level = record["extra"].get("__min_level")
    level_per_module = record["extra"].get("__level_per_module")
    if level_per_module:
        name = record["name"]
        level = min_level
        if name in level_per_module:
            level = level_per_module[name]
        elif name is not None:
            lookup = ""
            if "" in level_per_module:
                level = level_per_module[""]
            for n in name.split("."):
                lookup += n
                if lookup in level_per_module:
                    level = level_per_module[lookup]
                lookup += "."
        if level is False:
            return False
        return record["level"].no >= level
    level = record["extra"].get("__level_upper_only")
    if level:
        return record["level"].no >= logger.level(level).no
    return record["level"].no >= min_level


def conf_level_by_module(conf: dict):
    level_per_module = {}
    for module, level_ in conf.items():
        if module is not None and not isinstance(module, str):
            raise TypeError(
                "The filter dict contains an invalid module, "
                f"it should be a string (or None), not: '{type(module).__name__}'"
            )
        if level_ is False:
            levelno_ = False
        elif level_ is True:
            levelno_ = 0
        elif isinstance(level_, str):
            try:
                levelno_ = logger.level(level_).no
            except ValueError:
                raise ValueError(
                    f"The filter dict contains a module '{module}' associated to a level name "
                    f"which does not exist: '{level_}'"
                ) from None
        elif isinstance(level_, int):
            levelno_ = level_
        else:
            raise TypeError(
                f"The filter dict contains a module '{module}' associated to an invalid level, "
                f"it should be an integer, a string or a boolean, not: '{type(level_).__name__}'"
            )
        if levelno_ < 0:
            raise ValueError(
                f"The filter dict contains a module '{module}' associated to an invalid level, "
                "it should be a positive interger, not: '{levelno_}'"
            )
        level_per_module[module] = levelno_
    return level_per_module


class PropagateHandler(logging.Handler):
    def emit(self, record):
        logging.getLogger(record.name).handle(record)


def propagate_loguru_to_std_logger():
    logger.remove()
    logger.add(PropagateHandler(), format="{message}")


def reinstall_loguru(from_logger, target_logger):
    from_logger._core.__dict__ = target_logger._core.__dict__.copy()
    from_logger._options = target_logger._options
    extra_logger.update(target_logger._core.__dict__.get("extra", {}))


def mp_configure(logger_):
    """Configure a logger in a child process from a parent process logger.

    This function sets up the logger to work properly in multiprocessing contexts.
    It configures the basic logging system to use Loguru's InterceptHandler and
    reinstalls the logger with the configuration from the parent process.

    Args:
        logger_: The logger instance from the parent process to copy configuration from.
            This is typically passed from the parent process to child processes.

    Example:
        In the parent process:
        >>> init_logger("INFO")
        >>> from multiprocessing import Process
        >>> def worker(logger_instance):
        >>>     from logurich import mp_configure
        >>>     mp_configure(logger_instance)
        >>>     # Now the logger in this process has the same configuration
        >>>
        >>> p = Process(target=worker, args=(logger,))
        >>> p.start()
    """
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    reinstall_loguru(logger, logger_)


LogLevel = Literal[
    "TRACE",
    "DEBUG",
    "INFO",
    "SUCCESS",
    "WARNING",
    "ERROR",
    "CRITICAL",
]
LOG_LEVEL_CHOICES: tuple[str, ...] = get_args(LogLevel)


def init_logger(
    log_level: LogLevel,
    log_verbose: int = 0,
    log_filename: str = None,
    log_folder="logs",
    level_by_module=None,
    rich_handler: bool = False,
    diagnose: bool = False,
    enqueue: bool = True,
    highlight: bool = False,
) -> str:
    """Initialize and configure the logger with rich formatting and customized handlers.

    This function sets up a logging system using Loguru with optional Rich integration.
    It configures console output and optionally file-based logging with rotation.

    Args:
        log_level: The minimum logging level to display (e.g. "DEBUG", "INFO", "WARNING").
        log_verbose (int, optional): Controls the verbosity level of log formatting (0-3).
            0: Minimal format
            1: Include process name
            2: Include process name, module name and line number
            3: Include process name, thread name, module name and line number
            Defaults to 0.
        log_filename (str, optional): If provided, enables file logging with this filename.
            Defaults to None.
        log_folder (str, optional): The folder where log files will be stored.
            Defaults to "logs".
        level_by_module (dict, optional): Dictionary mapping module names to their specific
            log levels. Format: {"module.name": "LEVEL"}. Defaults to None.
        rich_handler (bool, optional): Whether to use Rich for enhanced console output.
            Can also be set via LOGURU_RICH environment variable. Defaults to False.
        diagnose (bool, optional): Whether to display variables in tracebacks.
            Defaults to False.
        enqueue (bool, optional): Whether to use a queue for thread-safe logging.
            Defaults to True.
        highlight (bool, optional): Whether to highlight log messages. Defaults to False.

    Returns:
        str: The absolute path to the log file if file logging is enabled, None otherwise.

    Example:
        >>> init_logger("INFO", log_verbose=2, log_filename="app.log")
        >>> logger.info("Application started")
        >>> logger.debug("Debug information")  # Won't be displayed with INFO level
    """
    rich_handler = (
        os.environ.get("LOGURU_RICH") if rich_handler is False else rich_handler
    )
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    logger.remove()
    if log_verbose > 3:
        log_verbose = 3
    elif log_verbose < 0:
        log_verbose = 0
    formatter = Formatter(log_level, log_verbose, is_rich_handler=rich_handler)
    level_per_module = (
        conf_level_by_module(level_by_module) if level_by_module else None
    )
    extra_logger.update(
        {
            "__level_per_module": level_per_module,
            "__min_level": logger.level(log_level).no,
            "__rich_highlight": highlight,
        }
    )
    logger.configure(extra=extra_logger, patcher=logger_patch)
    # Create appropriate handler based on rich_handler flag
    if rich_handler is True:
        handler = CustomRichHandler(
            rich_tracebacks=True,
            markup=True,
            tracebacks_show_locals=True,
        )
    else:
        handler = CustomHandler()
    # Add handler with common configuration
    logger.add(
        handler,
        level=0,
        format=formatter.format,
        filter=filter_records,
        enqueue=enqueue,
        diagnose=diagnose,
        colorize=False,
        serialize=os.environ.get("LOGURU_SERIALIZE"),
    )
    log_path = None
    if log_filename is not None:
        log_path = os.path.join(log_folder, log_filename)
        logger.add(
            log_path,
            level=0,
            rotation="12:00",
            retention="10 days",
            format=formatter.format_file,
            filter=filter_records,
            enqueue=True,
            serialize=False,
            diagnose=False,
            colorize=False,
        )
    return log_path
