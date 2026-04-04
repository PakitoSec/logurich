"""Core logging configuration and helpers for logurich."""

from __future__ import annotations

import contextlib
import contextvars
import copy
import logging
import logging.handlers
import multiprocessing as mp
import os
import traceback
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import time as datetime_time
from pathlib import Path
from typing import Any, Literal, Optional, Union, get_args

from rich.console import ConsoleRenderable
from rich.markup import escape
from rich.traceback import Traceback

from .handler import (
    CustomHandler,
    CustomRichHandler,
    LogurichFileFormatter,
    LogurichRenderer,
)
from .struct import logger_state
from .utils import parse_bool_env

_context_state: contextvars.ContextVar[dict[str, ContextValue] | None] = (
    contextvars.ContextVar("logurich_context_state", default=None)
)

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


def _normalize_style(style: Optional[str]) -> Optional[str]:
    if style is None:
        return None
    style = style.strip()
    if not style:
        return None
    return COLOR_ALIASES.get(style, style)


def _wrap_markup(style: Optional[str], text: str) -> str:
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
    """Display metadata for contextual log values."""

    value: Any
    value_style: Optional[str] = None
    bracket_style: Optional[str] = None
    label: Optional[str] = None
    show_key: bool = False

    def _label(self, key: str) -> Optional[str]:
        if self.label is not None:
            return self.label
        if self.show_key:
            return key
        return None

    def render(self, key: str, *, is_rich_handler: bool) -> str:
        label = self._label(key)
        value_text = escape(str(self.value))
        value_text = _wrap_markup(self.value_style, value_text)
        body = f"{escape(label)}={value_text}" if label else value_text
        if is_rich_handler:
            return body
        if _normalize_style(self.bracket_style):
            left = _wrap_markup(self.bracket_style, "[")
            right = _wrap_markup(self.bracket_style, "]")
        else:
            left = r"\["
            right = "]"
        return f"{left}{body}{right}"


def _normalize_context_key(key: str) -> str:
    if key.startswith("context::"):
        return key
    return f"context::{key}"


def _coerce_context_value(value: Any) -> Optional[ContextValue]:
    if value is None:
        return None
    if isinstance(value, ContextValue):
        return value
    return ContextValue(value=value)


def _get_context_state() -> dict[str, ContextValue]:
    current = _context_state.get()
    return dict(current) if current else {}


def _merge_context(raw_context: Any) -> dict[str, ContextValue]:
    merged = _get_context_state()
    if raw_context is None:
        return merged

    items = (
        raw_context.items()
        if isinstance(raw_context, Mapping)
        else [("context", raw_context)]
    )
    for key, value in items:
        normalized_key = _normalize_context_key(str(key))
        normalized_value = _coerce_context_value(value)
        if normalized_value is None:
            merged.pop(normalized_key, None)
            continue
        merged[normalized_key] = normalized_value
    return merged


def _load_env_extra() -> dict[str, str]:
    env_extra: dict[str, str] = {}
    for name, value in os.environ.items():
        if name.startswith("LOGURICH_EXTRA_"):
            env_extra[name.removeprefix("LOGURICH_EXTRA_")] = value
    return env_extra


def _coerce_level(level: Union[str, int]) -> int:
    if isinstance(level, int):
        if level < 0:
            raise ValueError("Log level must be a positive integer")
        return level
    normalized = level.upper()
    if normalized not in logging._nameToLevel or normalized == "NOTSET":
        raise ValueError(f"Unknown log level: {level}")
    return logging._nameToLevel[normalized]


_BaseLoggerClass = logging.getLoggerClass()


if hasattr(_BaseLoggerClass, "_logurich_logger_class"):
    LogurichLogger = _BaseLoggerClass
else:

    class LogurichLogger(_BaseLoggerClass):
        """Custom logger exposing Logurich convenience methods."""

        _logurich_logger_class = True

        def ctx(
            self,
            value: Any,
            *,
            style: Optional[str] = None,
            value_style: Optional[str] = None,
            bracket_style: Optional[str] = None,
            label: Optional[str] = None,
            show_key: Optional[bool] = None,
        ) -> ContextValue:
            return ctx(
                value,
                style=style,
                value_style=value_style,
                bracket_style=bracket_style,
                label=label,
                show_key=show_key,
            )

        def rich(
            self,
            log_level: Union[str, int],
            *renderables: Union[ConsoleRenderable, str],
            title: str = "",
            prefix: bool = True,
            end: str = "\n",
            width: Optional[int] = None,
        ) -> None:
            self.log(
                _coerce_level(log_level),
                title,
                extra={
                    "renderables": renderables,
                    "render_prefix": prefix,
                    "render_width": width,
                    "end": end,
                },
                stacklevel=2,
            )

        def bind(self, **kwargs: Any) -> BoundLogger:
            """Return a new :class:`BoundLogger` with *kwargs* pre-set as context."""
            bound_context: dict[str, ContextValue] = {}
            for key, value in kwargs.items():
                normalized_key = _normalize_context_key(key)
                coerced = _coerce_context_value(value)
                if coerced is not None:
                    bound_context[normalized_key] = coerced
            return BoundLogger(self, bound_context)

        def contextualize(
            self, **kwargs: Any
        ) -> contextlib.AbstractContextManager[None]:
            """Temporarily configure scoped context for this execution context."""
            return global_context_configure(**kwargs)


class BoundLogger(logging.LoggerAdapter):
    """Logger adapter that carries pre-bound context on every log call."""

    def __init__(
        self,
        logger_: Union[logging.Logger, logging.LoggerAdapter],
        bound_context: dict[str, ContextValue],
    ) -> None:
        # LoggerAdapter expects (logger, extra); we store context separately.
        super().__init__(
            logger_ if isinstance(logger_, logging.Logger) else logger_.logger,
            {},
        )
        self._bound_context = bound_context
        # Preserve chained context from a wrapped BoundLogger.
        if isinstance(logger_, BoundLogger):
            merged = dict(logger_._bound_context)
            merged.update(bound_context)
            self._bound_context = merged

    # -- public convenience methods (mirror LogurichLogger) ----------------

    def ctx(
        self,
        value: Any,
        *,
        style: Optional[str] = None,
        value_style: Optional[str] = None,
        bracket_style: Optional[str] = None,
        label: Optional[str] = None,
        show_key: Optional[bool] = None,
    ) -> ContextValue:
        return ctx(
            value,
            style=style,
            value_style=value_style,
            bracket_style=bracket_style,
            label=label,
            show_key=show_key,
        )

    def rich(
        self,
        log_level: Union[str, int],
        *renderables: Union[ConsoleRenderable, str],
        title: str = "",
        prefix: bool = True,
        end: str = "\n",
        width: Optional[int] = None,
    ) -> None:
        self.log(
            _coerce_level(log_level),
            title,
            extra={
                "renderables": renderables,
                "render_prefix": prefix,
                "render_width": width,
                "end": end,
            },
            stacklevel=2,
        )

    def bind(self, **kwargs: Any) -> BoundLogger:
        """Return a new :class:`BoundLogger` adding *kwargs* to the bound context."""
        new_context: dict[str, ContextValue] = {}
        for key, value in kwargs.items():
            normalized_key = _normalize_context_key(key)
            coerced = _coerce_context_value(value)
            if coerced is not None:
                new_context[normalized_key] = coerced
        return BoundLogger(self, new_context)

    def contextualize(self, **kwargs: Any) -> contextlib.AbstractContextManager[None]:
        """Temporarily configure scoped context for this execution context."""
        return global_context_configure(**kwargs)

    # -- adapter plumbing --------------------------------------------------

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        extra = kwargs.get("extra")
        merged_extra = {} if extra is None else dict(extra)
        # Merge: bound context first, then per-call context overrides.
        existing = merged_extra.get("context")
        merged: dict[str, Any] = dict(self._bound_context)
        if isinstance(existing, Mapping):
            merged.update(existing)
        elif existing is not None:
            merged["context"] = existing
        merged_extra["context"] = merged
        kwargs["extra"] = merged_extra
        return msg, kwargs


def _install_logger_class() -> None:
    logging.setLoggerClass(LogurichLogger)
    logging.RootLogger.ctx = LogurichLogger.ctx
    logging.RootLogger.rich = LogurichLogger.rich
    logging.RootLogger.bind = LogurichLogger.bind
    logging.RootLogger.contextualize = LogurichLogger.contextualize

    for existing in logging.Logger.manager.loggerDict.values():
        if isinstance(existing, logging.PlaceHolder):
            continue
        if isinstance(existing, LogurichLogger):
            continue
        with contextlib.suppress(TypeError):
            existing.__class__ = LogurichLogger


_install_logger_class()

logger: LogurichLogger = logging.getLogger("logurich")
logger.setLevel(logging.NOTSET)
logger.propagate = True


def _configure_level_by_module(
    conf: Mapping[str, Union[str, int]],
) -> dict[str, int]:
    level_per_module: dict[str, int] = {}
    for module, level in conf.items():
        if not isinstance(module, str):
            raise TypeError(
                "The filter dict contains an invalid module, "
                f"it should be a string, not: '{type(module).__name__}'"
            )
        level_per_module[module] = _coerce_level(level)
    return level_per_module


def _resolve_level_for_record(name: str) -> int:
    min_level = logger_state.get("min_level")
    if min_level is None:
        return logging.INFO

    level_per_module = logger_state.get("level_by_module") or {}
    if not level_per_module:
        return min_level

    level = level_per_module.get("", min_level)
    if name in level_per_module:
        return level_per_module[name]

    lookup = []
    for part in name.split("."):
        lookup.append(part)
        candidate = ".".join(lookup)
        if candidate in level_per_module:
            level = level_per_module[candidate]
    return level


class _ProducerFilter(logging.Filter):
    """Enrich log records before direct output or enqueueing."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "_logurich_prepared", False):
            return True

        record._logurich_prepared = True
        record.context = _merge_context(getattr(record, "context", None))
        record.renderables = self._normalize_renderables(
            getattr(record, "renderables", ())
        )
        record.render_prefix = getattr(record, "render_prefix", True)
        record.render_width = getattr(record, "render_width", None)
        record.end = getattr(record, "end", "\n")
        record.rich_highlight = bool(getattr(record, "rich_highlight", False))

        if record.exc_info:
            record.formatted_exception = "".join(
                traceback.format_exception(*record.exc_info)
            ).rstrip("\n")
            exc_type, exc_value, exc_traceback = record.exc_info
            if exc_type and exc_value:
                record.exception_data = {
                    "type": exc_type.__name__,
                    "value": str(exc_value),
                    "traceback": record.formatted_exception,
                }
                record.rich_traceback = Traceback.from_exception(
                    exc_type,
                    exc_value,
                    exc_traceback,
                    width=None,
                    extra_lines=3,
                    word_wrap=True,
                    show_locals=True,
                    locals_max_length=10,
                    locals_max_string=80,
                )
        else:
            record.formatted_exception = getattr(record, "formatted_exception", "")
            record.exception_data = getattr(record, "exception_data", None)
            record.rich_traceback = getattr(record, "rich_traceback", None)

        return True

    @staticmethod
    def _normalize_renderables(renderables: Any) -> tuple[Any, ...]:
        if renderables is None:
            return ()
        if isinstance(renderables, tuple):
            return tuple(item for item in renderables if item is not None)
        if isinstance(renderables, list):
            return tuple(item for item in renderables if item is not None)
        return (renderables,)


class _OutputFilter(logging.Filter):
    """Apply logger-level and per-module level filtering."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= _resolve_level_for_record(record.name)


class _LogurichQueueHandler(logging.handlers.QueueHandler):
    """Queue handler that preserves enriched log record attributes."""

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        prepared = copy.copy(record)
        _PRODUCER_FILTER.filter(prepared)
        prepared.message = prepared.getMessage()
        prepared.msg = prepared.message
        prepared.args = None
        prepared.exc_info = None
        prepared.exc_text = None
        prepared.stack_info = None
        return prepared


_PRODUCER_FILTER = _ProducerFilter()
_OUTPUT_FILTER = _OutputFilter()

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LOG_LEVEL_CHOICES: tuple[str, ...] = get_args(LogLevel)


def ctx(
    value: Any,
    *,
    style: Optional[str] = None,
    value_style: Optional[str] = None,
    bracket_style: Optional[str] = None,
    label: Optional[str] = None,
    show_key: Optional[bool] = None,
) -> ContextValue:
    """Build a ``ContextValue`` helper for structured context logging."""

    effective_value_style = value_style if value_style is not None else style
    return ContextValue(
        value=value,
        value_style=effective_value_style,
        bracket_style=bracket_style,
        label=label,
        show_key=bool(show_key) if show_key is not None else False,
    )


@contextlib.contextmanager
def global_context_configure(**kwargs: Any):
    """Temporarily configure scoped context for the current execution context."""

    updated = _get_context_state()
    for key, value in kwargs.items():
        normalized_key = _normalize_context_key(key)
        normalized_value = _coerce_context_value(value)
        if normalized_value is None:
            updated.pop(normalized_key, None)
            continue
        updated[normalized_key] = normalized_value
    token = _context_state.set(updated)
    try:
        yield
    finally:
        _context_state.reset(token)


def global_context_set(**kwargs: Any) -> None:
    """Set scoped context for subsequent log records in the current process."""

    updated = _get_context_state()
    for key, value in kwargs.items():
        normalized_key = _normalize_context_key(key)
        normalized_value = _coerce_context_value(value)
        if normalized_value is None:
            updated.pop(normalized_key, None)
            continue
        updated[normalized_key] = normalized_value
    _context_state.set(updated)


def _unique_handlers(*groups: list[logging.Handler]) -> list[logging.Handler]:
    unique: list[logging.Handler] = []
    seen: set[int] = set()
    for group in groups:
        for handler in group:
            if id(handler) in seen:
                continue
            seen.add(id(handler))
            unique.append(handler)
    return unique


def _close_handlers(handlers: list[logging.Handler]) -> None:
    for handler in handlers:
        with contextlib.suppress(Exception):
            handler.flush()
        with contextlib.suppress(Exception):
            handler.close()


def _remove_handlers(logger_: logging.Logger) -> list[logging.Handler]:
    handlers = list(logger_.handlers)
    for handler in handlers:
        logger_.removeHandler(handler)
    return handlers


def _build_console_handler(
    log_verbose: int, *, rich_handler: bool, serialize: bool
) -> logging.Handler:
    renderer = LogurichRenderer(log_verbose)
    if serialize or not rich_handler:
        handler: logging.Handler = CustomHandler(renderer, serialize=serialize)
    else:
        handler = CustomRichHandler(
            renderer,
            rich_tracebacks=True,
            markup=True,
            tracebacks_show_locals=True,
        )
    handler.setLevel(logging.NOTSET)
    handler.addFilter(_OUTPUT_FILTER)
    return handler


def _parse_rotation_time(rotation: str) -> datetime_time:
    parts = rotation.split(":", 1)
    if len(parts) != 2:
        raise ValueError(
            "rotation must be None, an integer, 'midnight', or a string in HH:MM format"
        )
    hour = int(parts[0])
    minute = int(parts[1])
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(
            "rotation must be None, an integer, 'midnight', or a string in HH:MM format"
        )
    return datetime_time(hour=hour, minute=minute)


def _build_file_handler(
    log_path: Path,
    *,
    log_verbose: int,
    serialize: bool,
    rotation: Optional[Union[str, int]],
    retention: Optional[int],
) -> logging.Handler:
    if retention is not None and (not isinstance(retention, int) or retention < 0):
        raise TypeError("retention must be a non-negative integer or None")

    if rotation is None:
        handler: logging.Handler = logging.FileHandler(log_path, encoding="utf-8")
    elif isinstance(rotation, int):
        if rotation <= 0:
            raise ValueError(
                "rotation must be a positive integer when using size-based rotation"
            )
        handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=rotation,
            backupCount=retention or 0,
            encoding="utf-8",
        )
    elif isinstance(rotation, str):
        if rotation == "midnight":
            handler = logging.handlers.TimedRotatingFileHandler(
                log_path,
                when="midnight",
                backupCount=retention or 0,
                encoding="utf-8",
            )
        else:
            handler = logging.handlers.TimedRotatingFileHandler(
                log_path,
                when="midnight",
                atTime=_parse_rotation_time(rotation),
                backupCount=retention or 0,
                encoding="utf-8",
            )
    else:
        raise TypeError(
            "rotation must be None, an integer, 'midnight', or a string in HH:MM format"
        )

    handler.setLevel(logging.NOTSET)
    handler.setFormatter(
        LogurichFileFormatter(LogurichRenderer(log_verbose), serialize=serialize)
    )
    handler.addFilter(_OUTPUT_FILTER)
    return handler


def shutdown_logger() -> None:
    """Stop queue listeners and close all configured handlers."""

    listener = logger_state.get("listener")
    if listener is not None:
        listener.stop()

    root = logging.getLogger()
    root_handlers = _remove_handlers(root)
    logger_handlers = _remove_handlers(logger)
    final_handlers = list(logger_state.get("final_handlers") or ())
    _close_handlers(_unique_handlers(root_handlers, logger_handlers, final_handlers))

    queue = logger_state.get("queue")
    if queue is not None:
        with contextlib.suppress(Exception):
            queue.close()
        with contextlib.suppress(Exception):
            queue.join_thread()

    logger_state.update(
        {
            "min_level": None,
            "level_by_module": None,
            "rich_highlight": False,
            "queue": None,
            "listener": None,
            "final_handlers": (),
            "env_extra": {},
        }
    )
    _context_state.set({})


def get_log_queue() -> mp.Queue:
    """Return the active multiprocessing queue used for logging."""

    queue = logger_state.get("queue")
    if queue is None:
        raise RuntimeError(
            "Logging queue is not configured. Initialize the logger with enqueue=True."
        )
    return queue


def configure_child_logging(queue: mp.Queue, logger_name: str = "logurich") -> None:
    """Configure a child process to forward logs to the parent logging queue."""

    root = logging.getLogger()
    _close_handlers(_remove_handlers(root))

    queue_handler = _LogurichQueueHandler(queue)
    queue_handler.setLevel(logging.NOTSET)
    queue_handler.addFilter(_PRODUCER_FILTER)

    root.addHandler(queue_handler)
    root.setLevel(logging.NOTSET)

    child_logger = logging.getLogger(logger_name)
    _close_handlers(_remove_handlers(child_logger))
    child_logger.setLevel(logging.NOTSET)
    child_logger.propagate = True

    logger_state.update(
        {
            "queue": queue,
            "listener": None,
            "final_handlers": (),
        }
    )


def init_logger(
    log_level: LogLevel,
    log_verbose: int = 0,
    log_filename: Optional[str] = None,
    log_folder: str = "logs",
    level_by_module: Optional[Mapping[str, Union[str, int]]] = None,
    *,
    rich_handler: bool = False,
    enqueue: bool = True,
    highlight: bool = False,
    rotation: Optional[Union[str, int]] = "12:00",
    retention: Optional[int] = 10,
) -> Optional[str]:
    """Initialize stdlib logging with optional Rich rendering and queue support."""

    shutdown_logger()

    env_rich_handler = parse_bool_env("LOGURICH_RICH")
    if env_rich_handler is not None:
        rich_handler = env_rich_handler

    serialize = bool(parse_bool_env("LOGURICH_SERIALIZE"))
    min_level = _coerce_level(log_level)
    module_levels = (
        _configure_level_by_module(level_by_module) if level_by_module else None
    )

    root = logging.getLogger()
    root.setLevel(logging.NOTSET)
    logger.setLevel(logging.NOTSET)
    logger.propagate = True

    logger_state.update(
        {
            "min_level": min_level,
            "level_by_module": module_levels,
            "rich_highlight": highlight,
            "env_extra": _load_env_extra(),
        }
    )

    console_handler = _build_console_handler(
        log_verbose, rich_handler=rich_handler, serialize=serialize
    )
    final_handlers: list[logging.Handler] = [console_handler]

    log_path: Optional[str] = None
    if log_filename is not None:
        log_dir = Path(log_folder)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_path = log_dir / log_filename
        final_handlers.append(
            _build_file_handler(
                file_path,
                log_verbose=log_verbose,
                serialize=serialize,
                rotation=rotation,
                retention=retention,
            )
        )
        log_path = str(file_path.resolve())

    if enqueue:
        queue = mp.Queue()
        queue_handler = _LogurichQueueHandler(queue)
        queue_handler.setLevel(logging.NOTSET)
        queue_handler.addFilter(_PRODUCER_FILTER)
        root.addHandler(queue_handler)

        listener = logging.handlers.QueueListener(
            queue,
            *final_handlers,
            respect_handler_level=True,
        )
        listener.start()
        logger_state.update(
            {
                "queue": queue,
                "listener": listener,
                "final_handlers": tuple(final_handlers),
            }
        )
    else:
        for handler in final_handlers:
            handler.addFilter(_PRODUCER_FILTER)
            root.addHandler(handler)
        logger_state.update(
            {
                "queue": None,
                "listener": None,
                "final_handlers": tuple(final_handlers),
            }
        )

    return log_path
