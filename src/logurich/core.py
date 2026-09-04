"""Core logging configuration and the public Logurich logger adapter."""

from __future__ import annotations

import atexit
import contextlib
import copy
import difflib
import logging
import logging.handlers
import multiprocessing as mp
import os
import pickle
import threading
import traceback
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import time as datetime_time
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional, Union, get_args

from rich.console import ConsoleRenderable
from rich.traceback import Traceback

from .console import rich_get_console, rich_to_str
from .context import (
    ContextValue,
    ctx,
    get_context,
    global_clear_context,
    global_context,
    normalize_context,
)
from .handler import (
    CustomHandler,
    CustomRichHandler,
    LogurichFileFormatter,
    LogurichRenderer,
    RichLayoutUnavailable,
)
from .struct import logger_state

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
ConsoleMode = Literal["auto", "rich", "plain", "json"]
FileMode = Literal["text", "json"]

LOG_LEVEL_CHOICES: tuple[str, ...] = get_args(LogLevel)
CONSOLE_MODE_CHOICES: tuple[str, ...] = get_args(ConsoleMode)
FILE_MODE_CHOICES: tuple[str, ...] = get_args(FileMode)

# Logurich reserves no call keywords of its own; rendering options live on rich().
_STDLIB_CALL_KWARGS = frozenset({"exc_info", "stack_info", "stacklevel", "extra"})
_METADATA_KWARG = "_logurich_meta"
_LEGACY_EXTRA_KEYS = frozenset({"context", "renderables"})
_STANDARD_LOG_RECORD_ATTRS = frozenset(logging.makeLogRecord({}).__dict__)
_RESERVED_CALL_KWARGS = tuple(sorted(_STDLIB_CALL_KWARGS))

LogLevels = tuple[int, Optional[dict[str, int]]]


@dataclass(frozen=True)
class _OutputModes:
    """Resolved and validated output modes used by ``init_logger``."""

    console: str
    file: str


def _normalise_choice(value: Any, choices: tuple[str, ...], name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string, not {type(value).__name__}")
    normalised = value.strip().lower()
    if normalised not in choices:
        allowed = ", ".join(choices)
        raise ValueError(f"Invalid {name} mode {value!r}; expected one of: {allowed}")
    return normalised


def _resolve_output_modes(
    *,
    console: str,
    file: str,
    is_terminal: bool,
    env: Optional[Mapping[str, str]] = None,
) -> _OutputModes:
    """Validate output modes and deterministically resolve ``console='auto'``."""

    environment = {} if env is None else env
    resolved_console = _normalise_choice(console, CONSOLE_MODE_CHOICES, "console")
    env_console = environment.get("LOGURICH_OUTPUT")
    if env_console is not None:
        try:
            resolved_console = _normalise_choice(
                env_console, CONSOLE_MODE_CHOICES, "LOGURICH_OUTPUT"
            )
        except ValueError as error:
            # A bad env var must not take down the application at startup.
            warnings.warn(
                f"{error}; falling back to console={resolved_console!r}", stacklevel=3
            )
    resolved_file = _normalise_choice(file, FILE_MODE_CHOICES, "file")
    if resolved_console == "auto":
        resolved_console = "plain" if is_terminal else "json"
    return _OutputModes(console=resolved_console, file=resolved_file)


@lru_cache(maxsize=512)
def _misspelled_call_kwarg(key: str) -> Optional[str]:
    """Return the reserved keyword ``key`` most likely misspells, if any."""

    matches = difflib.get_close_matches(key, _RESERVED_CALL_KWARGS, n=1, cutoff=0.85)
    return matches[0] if matches else None


def _coerce_level(level: Union[str, int]) -> int:
    if isinstance(level, bool):
        raise TypeError("Log level must be a string or integer")
    if isinstance(level, int):
        if level < 0:
            raise ValueError("Log level must be a non-negative integer")
        return level
    if not isinstance(level, str):
        raise TypeError("Log level must be a string or integer")
    normalized = level.upper()
    if normalized not in logging._nameToLevel or normalized == "NOTSET":
        raise ValueError(f"Unknown log level: {level}")
    return logging._nameToLevel[normalized]


class LogurichLogger(logging.LoggerAdapter):
    """Explicit Logurich wrapper around an unmodified stdlib logger."""

    def __init__(
        self,
        logger: logging.Logger,
        bound_context: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(logger, {})
        self._bound_context = normalize_context(bound_context or {})

    @property
    def name(self) -> str:
        return self.logger.name

    @property
    def level(self) -> int:
        return self.logger.level

    @level.setter
    def level(self, value: int) -> None:
        self.logger.setLevel(value)

    @property
    def handlers(self) -> list[logging.Handler]:
        return self.logger.handlers

    @handlers.setter
    def handlers(self, value: list[logging.Handler]) -> None:
        self.logger.handlers = value

    @property
    def propagate(self) -> bool:
        return self.logger.propagate

    @propagate.setter
    def propagate(self, value: bool) -> None:
        self.logger.propagate = value

    @property
    def disabled(self) -> bool:
        return self.logger.disabled

    @disabled.setter
    def disabled(self, value: bool) -> None:
        self.logger.disabled = value

    def setLevel(self, level: Union[int, str]) -> None:
        self.logger.setLevel(level)

    def isEnabledFor(self, level: int) -> bool:
        return self.logger.isEnabledFor(level)

    def addHandler(self, handler: logging.Handler) -> None:
        self.logger.addHandler(handler)

    def removeHandler(self, handler: logging.Handler) -> None:
        self.logger.removeHandler(handler)

    @staticmethod
    def _validate_legacy_extra(extra: Any) -> None:
        if not isinstance(extra, Mapping):
            return
        legacy = sorted(_LEGACY_EXTRA_KEYS.intersection(extra))
        if not legacy:
            return
        key = legacy[0]
        if key == "context":
            replacement = "pass context as keyword arguments"
        else:
            replacement = "use logger.rich(level, *renderables, ...)"
        raise TypeError(f"extra={{'{key}': ...}} is no longer supported; {replacement}")

    @staticmethod
    def _validate_call_kwargs(kwargs: Mapping[str, Any]) -> None:
        if "renderables" in kwargs:
            raise TypeError(
                "'renderables' is not a logging keyword; "
                "use logger.rich(level, *renderables, ...)"
            )

    def log(self, level: int, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Validate removed APIs even when a record would be filtered out."""

        self._validate_legacy_extra(kwargs.get("extra"))
        self._validate_call_kwargs(kwargs)
        if not self.isEnabledFor(level):
            return
        # Bypass LoggerAdapter.log: findCaller only skips its frame on 3.11+.
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        msg, kwargs = self.process(msg, kwargs)
        self.logger.log(level, msg, *args, **kwargs)

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
        highlight: bool = False,
    ) -> None:
        """Log live Rich renderables without rendering them at the call site."""

        if width is not None and width < 1:
            raise ValueError("width must be >= 1")
        self.log(
            _coerce_level(log_level),
            title,
            stacklevel=2,
            **{
                _METADATA_KWARG: {
                    "renderables": renderables,
                    "render_prefix": prefix,
                    "render_width": width,
                    "end": end,
                    "rich_highlight": highlight,
                }
            },
        )

    def bind(self, **values: Any) -> LogurichLogger:
        """Return a new adapter with additional immutable bound context."""

        merged = dict(self._bound_context)
        merged.update(normalize_context(values))
        return type(self)(self.logger, merged)

    def new(self, **values: Any) -> LogurichLogger:
        """Return a new adapter whose bound context is exactly ``values``."""

        return type(self)(self.logger, values)

    def unbind(self, *keys: str) -> LogurichLogger:
        """Return a new adapter without ``keys``, failing for missing keys."""

        unique_keys = tuple(dict.fromkeys(keys))
        missing = [key for key in unique_keys if key not in self._bound_context]
        if missing:
            raise KeyError(missing[0])
        remaining = dict(self._bound_context)
        for key in unique_keys:
            del remaining[key]
        return type(self)(self.logger, remaining)

    def try_unbind(self, *keys: str) -> LogurichLogger:
        """Return a new adapter without ``keys``, ignoring missing keys."""

        remaining = dict(self._bound_context)
        for key in keys:
            remaining.pop(key, None)
        return type(self)(self.logger, remaining)

    def contextualize(self, **values: Any) -> contextlib.AbstractContextManager[None]:
        """Temporarily extend context for the current execution."""

        return global_context(**values)

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        """Split stdlib options from per-call context."""

        supplied_extra = kwargs.get("extra")
        if supplied_extra is None:
            merged_extra: dict[str, Any] = {}
        elif isinstance(supplied_extra, Mapping):
            merged_extra = dict(supplied_extra)
        else:
            raise TypeError("extra must be a mapping or None")

        self._validate_legacy_extra(merged_extra)

        metadata: dict[str, Any] = kwargs.pop(_METADATA_KWARG, None) or {}
        call_context: dict[str, Any] = {
            key: kwargs.pop(key)
            for key in tuple(kwargs)
            if key not in _STDLIB_CALL_KWARGS
        }

        context = dict(self._bound_context)
        context.update(normalize_context(call_context))

        for key in call_context:
            suggestion = _misspelled_call_kwarg(key)
            if suggestion is not None:
                # Frames: process -> log -> info/debug/... -> caller.
                warnings.warn(
                    f"{key!r} is not a logging keyword and was recorded as "
                    f"context; did you mean {suggestion!r}?",
                    stacklevel=4,
                )

        merged_extra.update(metadata)
        merged_extra["context"] = context
        merged_extra["_logurich_record"] = True
        merged_extra["_logurich_metadata"] = tuple(metadata)
        kwargs["extra"] = merged_extra
        return msg, kwargs


def get_logger(name: Optional[str] = None) -> LogurichLogger:
    """Return a new Logurich adapter around the named stdlib logger."""

    return LogurichLogger(logging.getLogger(name))


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
        return logging.NOTSET

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


def _user_extra(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _STANDARD_LOG_RECORD_ATTRS
        and key != "message"
        and not key.startswith("_logurich_")
    }


class _ProducerFilter(logging.Filter):
    """Normalise a LogRecord once, before direct output or enqueueing."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "_logurich_prepared", False):
            return True

        is_logurich_record = bool(getattr(record, "_logurich_record", False))
        metadata = set(getattr(record, "_logurich_metadata", ()))
        context = get_context()
        extras = _user_extra(record)

        if is_logurich_record:
            extras.pop("context", None)
            for key in metadata:
                extras.pop(key, None)
            context.update(normalize_context(extras))
            raw_context = getattr(record, "context", {})
            if isinstance(raw_context, Mapping):
                context.update(normalize_context(raw_context))
        else:
            context.update(normalize_context(extras))

        record.context = context
        record.renderables = self._normalize_renderables(
            getattr(record, "renderables", ())
            if is_logurich_record and "renderables" in metadata
            else ()
        )
        record.render_prefix = (
            getattr(record, "render_prefix", True)
            if "render_prefix" in metadata
            else True
        )
        record.render_width = (
            getattr(record, "render_width", None)
            if "render_width" in metadata
            else None
        )
        record.end = getattr(record, "end", "\n") if "end" in metadata else "\n"
        record.rich_highlight = bool(
            getattr(record, "rich_highlight", False)
            if "rich_highlight" in metadata
            else False
        )

        record.formatted_stack = record.stack_info or ""
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

        record._logurich_prepared = True
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
    """Apply the configured global and per-module levels."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= _resolve_level_for_record(record.name)


class _LogurichQueueHandler(logging.handlers.QueueHandler):
    """Queue handler preserving serialisable Rich values for the listener."""

    @staticmethod
    def _safe_renderables(record: logging.LogRecord) -> tuple[Any, ...]:
        safe: list[Any] = []
        for renderable in getattr(record, "renderables", ()):
            try:
                pickle.dumps(renderable)
            except Exception:
                safe.append(rich_to_str(renderable, ansi=False, end="").rstrip("\n"))
            else:
                safe.append(renderable)
        return tuple(safe)

    @staticmethod
    def _requires_pickle_validation(record: logging.LogRecord) -> bool:
        """Return whether the normalised record retains non-standard values."""

        return bool(
            record.context or record.renderables or record.rich_traceback is not None
        )

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        prepared = copy.copy(record)
        _PRODUCER_FILTER.filter(prepared)
        prepared.message = prepared.getMessage()
        prepared.msg = prepared.message
        prepared.args = None
        prepared.exc_info = None
        prepared.exc_text = None
        prepared.stack_info = None
        if not self._requires_pickle_validation(prepared):
            return prepared
        try:
            pickle.dumps(prepared)
        except Exception as error:
            if not prepared.renderables:
                raise TypeError(
                    "LogRecord cannot be sent through the multiprocessing queue; "
                    "use serialisable context values"
                ) from error

            prepared.renderables = self._safe_renderables(prepared)
            try:
                pickle.dumps(prepared)
            except Exception as fallback_error:
                raise TypeError(
                    "LogRecord cannot be sent through the multiprocessing queue; "
                    "use serialisable context values"
                ) from fallback_error
        return prepared


_PRODUCER_FILTER = _ProducerFilter()
_OUTPUT_FILTER = _OutputFilter()


def _load_env_extra() -> dict[str, str]:
    env_extra: dict[str, str] = {}
    for name, value in os.environ.items():
        if name.startswith("LOGURICH_EXTRA_"):
            env_extra[name.removeprefix("LOGURICH_EXTRA_")] = value
    return env_extra


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


def _remove_installed_handlers() -> list[logging.Handler]:
    root = logging.getLogger()
    handlers = list(logger_state.get("installed_handlers") or ())
    for handler in handlers:
        root.removeHandler(handler)
    return handlers


def _clear_root_handlers() -> None:
    """Drop every root handler so Logurich becomes the single sink.

    Handlers Logurich built (they all carry ``_OUTPUT_FILTER``) are closed;
    foreign ones are only detached, since the host runtime owns their resources
    — closing them could take down a file descriptor it still writes to.
    """

    root = logging.getLogger()
    superseded: list[logging.Handler] = []
    for handler in list(root.handlers):
        root.removeHandler(handler)
        if _OUTPUT_FILTER in handler.filters:
            superseded.append(handler)
    _close_handlers(superseded)


def _configure_handler(handler: logging.Handler, *, producer: bool) -> None:
    handler.setLevel(logging.NOTSET)
    handler.addFilter(_OUTPUT_FILTER)
    if producer:
        handler.addFilter(_PRODUCER_FILTER)


def _build_console_handler(log_verbose: int, *, mode: str) -> logging.Handler:
    renderer = LogurichRenderer(log_verbose)
    if mode == "rich":
        try:
            handler: logging.Handler = CustomRichHandler(
                renderer,
                rich_tracebacks=True,
                markup=True,
                tracebacks_show_locals=True,
            )
        except RichLayoutUnavailable as error:
            warnings.warn(f"{error}; falling back to console='plain'", stacklevel=3)
            handler = CustomHandler(renderer, serialize=False)
    else:
        handler = CustomHandler(renderer, serialize=mode == "json")
    _configure_handler(handler, producer=False)
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
    mode: str,
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

    handler.setFormatter(
        LogurichFileFormatter(LogurichRenderer(log_verbose), serialize=mode == "json")
    )
    handler.terminator = ""  # type: ignore[attr-defined]
    _configure_handler(handler, producer=False)
    return handler


def shutdown_logger() -> None:
    """Stop Logurich's listener and close only handlers owned by Logurich."""

    listener = logger_state.get("listener")
    if listener is not None:
        with contextlib.suppress(Exception):
            listener.stop()

    installed_handlers = _remove_installed_handlers()
    final_handlers = list(logger_state.get("final_handlers") or ())
    _close_handlers(_unique_handlers(installed_handlers, final_handlers))

    queue = logger_state.get("queue")
    if queue is not None:
        with contextlib.suppress(Exception):
            queue.close()
        with contextlib.suppress(Exception):
            queue.join_thread()

    original_root_level = logger_state.get("original_root_level")
    if original_root_level is not None:
        logging.getLogger().setLevel(original_root_level)

    logger_state.update(
        {
            "min_level": None,
            "level_by_module": None,
            "rich_highlight": False,
            "queue": None,
            "listener": None,
            "final_handlers": (),
            "installed_handlers": (),
            "env_extra": {},
            "output_modes": None,
            "original_root_level": None,
        }
    )
    global_clear_context()


def _ensure_shutdown_atexit_registered() -> None:
    if logger_state.get("atexit_registered"):
        return
    atexit.register(shutdown_logger)
    logger_state["atexit_registered"] = True


def _ensure_shutdown_threading_atexit_registered() -> None:
    if logger_state.get("threading_atexit_registered"):
        return
    register = getattr(threading, "_register_atexit", None)
    if register is None:
        return
    register(shutdown_logger)
    logger_state["threading_atexit_registered"] = True


def get_log_queue() -> mp.Queue:
    """Return the active multiprocessing logging queue."""

    queue = logger_state.get("queue")
    if queue is None:
        raise RuntimeError(
            "Logging queue is not configured. Initialize the logger with enqueue=True."
        )
    return queue


def get_log_levels() -> LogLevels:
    """Return the configured levels, to hand to ``configure_child_logging``."""

    min_level = logger_state.get("min_level")
    if min_level is None:
        raise RuntimeError("Logging is not configured. Call init_logger() first.")
    level_by_module = logger_state.get("level_by_module")
    return (min_level, dict(level_by_module) if level_by_module else None)


def _level_floor(min_level: int, level_by_module: Optional[Mapping[str, int]]) -> int:
    """Return the lowest level that any configured logger may emit."""

    return min([min_level, *(level_by_module or {}).values()])


def _apply_child_levels(levels: Optional[LogLevels], root: logging.Logger) -> None:
    """Adopt the parent's levels so the worker filters before building records."""

    if levels is None:
        root.setLevel(logging.NOTSET)
        return

    min_level, level_by_module = levels
    logger_state.update({"min_level": min_level, "level_by_module": level_by_module})
    # Permissive floor only; _OUTPUT_FILTER still applies the per-module levels.
    root.setLevel(_level_floor(min_level, level_by_module))


def configure_child_logging(
    queue: mp.Queue,
    logger_name: str = "logurich",
    *,
    levels: Optional[LogLevels] = None,
) -> None:
    """Forward a worker's stdlib records to the parent's Logurich queue.

    Pass ``levels=get_log_levels()`` from the parent to drop filtered records in
    the worker; without it the worker enqueues everything and the parent filters.
    """

    root = logging.getLogger()
    inherited_handlers = list(root.handlers)
    for handler in inherited_handlers:
        root.removeHandler(handler)
    _close_handlers(inherited_handlers)

    queue_handler = _LogurichQueueHandler(queue)
    _configure_handler(queue_handler, producer=True)
    root.addHandler(queue_handler)
    _apply_child_levels(levels, root)

    child_logger = logging.getLogger(logger_name)
    child_logger.setLevel(logging.NOTSET)
    child_logger.propagate = True

    logger_state.update(
        {
            "queue": queue,
            "listener": None,
            "final_handlers": (),
            "installed_handlers": (queue_handler,),
        }
    )


def _warn_legacy_environment(env: Mapping[str, str]) -> None:
    legacy = [name for name in ("LOGURICH_RICH", "LOGURICH_SERIALIZE") if name in env]
    if legacy:
        names = ", ".join(legacy)
        verb = "are" if len(legacy) > 1 else "is"
        warnings.warn(
            f"{names} {verb} no longer supported and {verb} ignored; use "
            "LOGURICH_OUTPUT and the console/file arguments",
            stacklevel=3,
        )


def init_logger(
    log_level: Union[LogLevel, str, int],
    log_verbose: int = 0,
    log_filename: Optional[str] = None,
    log_folder: str = "logs",
    level_by_module: Optional[Mapping[str, Union[str, int]]] = None,
    *,
    console: ConsoleMode = "plain",
    file: FileMode = "text",
    enqueue: bool = True,
    highlight: bool = False,
    rotation: Optional[Union[str, int]] = "12:00",
    retention: Optional[int] = 10,
    force: bool = False,
    clear_handlers: bool = True,
) -> Optional[str]:
    """Configure stdlib logging with independent console and file formats.

    ``LOGURICH_OUTPUT``, when set, takes precedence over ``console`` and does
    not affect ``file``.

    ``clear_handlers`` drops every root handler, so Logurich becomes the single
    sink. Set it to ``False`` to leave handlers installed by a host runtime (AWS
    Lambda, gunicorn, an APM agent) in place — they then also receive Logurich
    records, which carry Rich objects a foreign formatter may not handle.
    """

    _warn_legacy_environment(os.environ)
    modes = _resolve_output_modes(
        console=console,
        file=file,
        is_terminal=rich_get_console().is_terminal,
        env=os.environ,
    )
    min_level = _coerce_level(log_level)
    module_levels = (
        _configure_level_by_module(level_by_module) if level_by_module else None
    )

    if not force and logger_state.get("min_level") is not None:
        return None

    _ensure_shutdown_threading_atexit_registered()
    _ensure_shutdown_atexit_registered()
    shutdown_logger()

    root = logging.getLogger()
    original_root_level = root.level
    # Reject records below every configured threshold before constructing them.
    # _OUTPUT_FILTER still applies the exact per-module level at the handler.
    root.setLevel(_level_floor(min_level, module_levels))

    if clear_handlers:
        _clear_root_handlers()

    logger_state.update(
        {
            "min_level": min_level,
            "level_by_module": module_levels,
            "rich_highlight": highlight,
            "env_extra": _load_env_extra(),
            "output_modes": modes,
            "original_root_level": original_root_level,
        }
    )

    console_handler = _build_console_handler(log_verbose, mode=modes.console)
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
                mode=modes.file,
                rotation=rotation,
                retention=retention,
            )
        )
        log_path = str(file_path.resolve())

    installed_handlers: list[logging.Handler]
    if enqueue:
        queue = mp.Queue()
        queue_handler = _LogurichQueueHandler(queue)
        _configure_handler(queue_handler, producer=True)
        root.addHandler(queue_handler)
        installed_handlers = [queue_handler]

        listener = logging.handlers.QueueListener(
            queue,
            *final_handlers,
            respect_handler_level=True,
        )
        listener.start()
        logger_state.update({"queue": queue, "listener": listener})
    else:
        for handler in final_handlers:
            handler.addFilter(_PRODUCER_FILTER)
            root.addHandler(handler)
        installed_handlers = final_handlers
        logger_state.update({"queue": None, "listener": None})

    logger_state.update(
        {
            "final_handlers": tuple(final_handlers),
            "installed_handlers": tuple(installed_handlers),
        }
    )
    return log_path
