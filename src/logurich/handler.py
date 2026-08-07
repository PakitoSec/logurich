"""Custom logging handlers for logurich."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from importlib.metadata import version as metadata_version
from logging import Formatter, Handler, LogRecord
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, Optional, Union

from rich.console import ConsoleRenderable, Group
from rich.constrain import Constrain
from rich.highlighter import ReprHighlighter
from rich.logging import RichHandler
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text

from .console import rich_console_renderer, rich_get_console, rich_to_str
from .serialize import serialize_renderables
from .struct import logger_state

if TYPE_CHECKING:
    from rich.console import Console, RenderableType

DEFAULT_CONTENT_PADDING = (0, 10, 22, 25)
SERIALIZATION_START = perf_counter()
STANDARD_LOG_RECORD_ATTRS = frozenset(logging.makeLogRecord({}).__dict__)
LOGURICH_INTERNAL_RECORD_ATTRS = frozenset(
    {
        "_logurich_prepared",
        "context",
        "end",
        "exception_data",
        "formatted_exception",
        "formatted_stack",
        "message",
        "render_prefix",
        "render_width",
        "renderables",
        "rich_highlight",
        "rich_traceback",
    }
)


def _safe_text_from_markup(value: str) -> Text:
    try:
        return Text.from_markup(value)
    except Exception:
        return Text(value)


def _installed_rich_version() -> str:
    try:
        return metadata_version("rich")
    except Exception:
        return "(unknown version)"


class LogurichRenderer:
    """Render log records for console, file, and JSON outputs."""

    LEVEL_COLOR_MAP = {
        "DEBUG": "bold blue",
        "INFO": "bold",
        "WARNING": "bold yellow",
        "ERROR": "bold red",
        "CRITICAL": "bold white on red",
    }

    def __init__(self, verbose: int) -> None:
        self.verbose = max(0, min(verbose, 3))
        self.base_padding = DEFAULT_CONTENT_PADDING[self.verbose]

    def build_context(self, record: LogRecord, *, is_rich_handler: bool) -> list[str]:
        list_context: list[str] = []
        context = getattr(record, "context", {}) or {}
        for name, value in context.items():
            if hasattr(value, "render"):
                list_context.append(value.render(name, is_rich_handler=is_rich_handler))
            else:
                list_context.append(f"[{name}={value}]")
        return list_context

    def build_prefix(self, record: LogRecord) -> str:
        time_text = datetime.fromtimestamp(record.created).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]
        level = record.levelname
        level_color = self.LEVEL_COLOR_MAP.get(level, "cyan")
        source = self._source_label(record)
        if not source:
            return f"{time_text} | [{level_color}]{level:<8}[/{level_color}] | "
        target_padding = min(max(self.base_padding, len(source)), 50)
        padding = " " * max(0, target_padding - len(source))
        return (
            f"{time_text} | [{level_color}]{level:<8}[/{level_color}] | "
            f"{source}{padding} | "
        )

    def format_file(
        self, record: LogRecord, *, renderables: Optional[tuple[Any, ...]] = None
    ) -> str:
        prefix_markup = self.build_prefix(record)
        prefix_plain = _safe_text_from_markup(prefix_markup).plain
        context_markup = "".join(self.build_context(record, is_rich_handler=False))
        context_plain = _safe_text_from_markup(
            context_markup + (" " if context_markup else "")
        ).plain
        message_plain = _safe_text_from_markup(record.getMessage()).plain
        exception_text = getattr(record, "formatted_exception", "").rstrip("\n")
        stack_text = getattr(record, "formatted_stack", "").rstrip("\n")

        items = self._renderables(record) if renderables is None else renderables

        parts: list[str] = []
        if message_plain or not items:
            line = f"{prefix_plain}{context_plain}{message_plain}"
            if stack_text:
                line = f"{line}\n{stack_text}" if line else stack_text
            if exception_text:
                line = f"{line}\n{exception_text}" if line else exception_text
            parts.append(line)

        if items:
            rendered = rich_console_renderer(
                prefix_markup,
                getattr(record, "render_prefix", True),
                items,
                getattr(record, "render_width", None),
            )
            parts.append(
                rich_to_str(
                    *rendered,
                    ansi=False,
                    width=getattr(record, "render_width", None),
                ).rstrip("\n")
            )
        elif exception_text and not parts:
            parts.append(exception_text)

        return "\n".join(part for part in parts if part)

    def format_json(self, record: LogRecord) -> str:
        renderables = self._renderables(record)
        text_items = tuple(item for item in renderables if isinstance(item, str))
        rich_items = tuple(item for item in renderables if not isinstance(item, str))
        text = self.format_file(record, renderables=text_items)
        end = getattr(record, "end", "\n")
        rendered_text = f"{text}{end}" if text else ""
        extra = self._serialize_extra(record)
        created_at = datetime.fromtimestamp(record.created).astimezone()
        exception_data = getattr(record, "exception_data", None)
        file_path = str(Path(record.pathname))
        elapsed_seconds = perf_counter() - SERIALIZATION_START
        message_value = record.getMessage()
        if text_items and text:
            lines = text.splitlines()
            continuation = "\n".join(lines[1:])
            if continuation:
                message_value = f"{message_value}\n{continuation}"
        payload: dict[str, Any] = {
            "text": rendered_text,
            "record": {
                "elapsed": {
                    "repr": str(timedelta(seconds=elapsed_seconds)),
                    "seconds": round(elapsed_seconds, 6),
                },
                "exception": exception_data,
                "extra": extra,
                "file": {
                    "name": Path(record.pathname).name,
                    "path": file_path,
                },
                "function": record.funcName,
                "level": {
                    "name": record.levelname,
                    "no": record.levelno,
                },
                "line": record.lineno,
                "message": message_value,
                "module": record.module,
                "name": record.name,
                "process": {
                    "id": record.process,
                    "name": record.processName,
                },
                "thread": {
                    "id": record.thread,
                    "name": record.threadName,
                },
                "time": {
                    "repr": created_at.isoformat(),
                    "timestamp": record.created,
                },
            },
        }
        if rich_items:
            payload["record"]["renderables"] = serialize_renderables(rich_items)
        return json.dumps(payload, default=str, ensure_ascii=False)

    def _serialize_extra(self, record: LogRecord) -> dict[str, Any]:
        context = getattr(record, "context", {}) or {}
        serialized = dict(logger_state.get("env_extra", {}))
        user_extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in STANDARD_LOG_RECORD_ATTRS
            and key not in LOGURICH_INTERNAL_RECORD_ATTRS
            and not key.startswith("_logurich_")
        }
        if user_extra:
            serialized.update(user_extra)
        serialized.update(
            {key: getattr(value, "value", value) for key, value in context.items()}
        )
        return serialized

    def _renderables(self, record: LogRecord) -> tuple[Any, ...]:
        renderables = getattr(record, "renderables", ()) or ()
        if isinstance(renderables, tuple):
            return renderables
        if isinstance(renderables, list):
            return tuple(renderables)
        return (renderables,)

    def _source_label(self, record: LogRecord) -> str:
        if self.verbose == 1:
            return record.processName
        if self.verbose == 2:
            return f"{record.processName}.{record.name}:{record.lineno}"
        if self.verbose >= 3:
            return (
                f"{record.processName}.{record.threadName}."
                f"{record.name}:{record.lineno}"
            )
        return ""


class LogurichFileFormatter(Formatter):
    """Format log records for file output."""

    def __init__(self, renderer: LogurichRenderer, *, serialize: bool) -> None:
        super().__init__()
        self.renderer = renderer
        self.serialize = serialize

    def format(self, record: LogRecord) -> str:
        if self.serialize:
            formatted = self.renderer.format_json(record)
            end = "\n"
        else:
            formatted = self.renderer.format_file(record)
            end = getattr(record, "end", "\n")
        return f"{formatted}{end}"


class RichLayoutUnavailable(RuntimeError):
    """Raised when Rich no longer exposes the log layout ``console='rich'`` needs."""


class CustomRichHandler(RichHandler):
    """Rich-formatted handler using standard log records."""

    def __init__(
        self, renderer: LogurichRenderer, *args: object, **kwargs: object
    ) -> None:
        self.renderer = renderer
        super().__init__(*args, console=rich_get_console(), **kwargs)
        if not callable(getattr(self, "_log_render", None)):
            raise RichLayoutUnavailable(
                f"rich {_installed_rich_version()} does not provide "
                "RichHandler._log_render, which console='rich' renders through"
            )

    def build_content(self, record: LogRecord, content: RenderableType) -> Table:
        row: list[Union[str, RenderableType]] = []
        list_context = self.renderer.build_context(record, is_rich_handler=True)
        grid = Table.grid(expand=True)
        if list_context:
            grid.add_column(justify="left", style="bold", vertical="middle")
            row.append(".".join(list_context) + " :arrow_forward:  ")
        grid.add_column(
            ratio=1, style="log.message", overflow="fold", vertical="middle"
        )
        row.append(content)
        grid.add_row(*row)
        return grid

    def render(
        self,
        *,
        record: LogRecord,
        traceback: object,
        message_renderable: RenderableType,
    ) -> RenderableType:
        path = Path(record.pathname).name
        level = self.get_level_text(record)
        time_format = None if self.formatter is None else self.formatter.datefmt
        log_time = datetime.fromtimestamp(record.created)
        rich_tb = getattr(record, "rich_traceback", None)
        renderables = list(self.renderer._renderables(record))
        message_output: list[RenderableType] = []
        rich_output: list[RenderableType] = []
        diagnostic_output: list[RenderableType] = []
        render_width = getattr(record, "render_width", None)

        if record.getMessage():
            message_output.append(self.build_content(record, message_renderable))
        for item in renderables:
            if isinstance(item, (ConsoleRenderable, str)):
                renderable: RenderableType = item
            else:
                renderable = Pretty(item)
            if render_width is not None:
                renderable = Constrain(renderable, width=render_width)
            rich_output.append(renderable)
        stack_text = getattr(record, "formatted_stack", "").rstrip("\n")
        if stack_text and record.stack_info is None:
            diagnostic_output.append(Text(stack_text))
        if rich_tb is not None:
            diagnostic_output.append(rich_tb)

        render_prefix = getattr(record, "render_prefix", True)
        if render_prefix or not renderables:
            return self._log_render(
                self.console,
                message_output + rich_output + diagnostic_output,
                log_time=log_time,
                time_format=time_format,
                level=level,
                path=path,
                line_no=record.lineno,
                link_path=record.pathname if self.enable_link_path else None,
            )

        result: list[RenderableType] = []
        if message_output or diagnostic_output:
            result.append(
                self._log_render(
                    self.console,
                    message_output + diagnostic_output,
                    log_time=log_time,
                    time_format=time_format,
                    level=level,
                    path=path,
                    line_no=record.lineno,
                    link_path=record.pathname if self.enable_link_path else None,
                )
            )
        result.extend(rich_output)
        return Group(*result)

    def emit(self, record: LogRecord) -> None:
        """Emit with the per-record ``end`` contract used by ``logger.rich``.

        Derived from ``rich.logging.RichHandler.emit``, which hardcodes
        ``end="\\n"``, and relies on the private ``_log_render`` attribute.
        """

        try:
            message = self.format(record)
            if getattr(record, "rich_traceback", None) is not None and record.exc_info:
                message = record.getMessage()
                if self.formatter is not None:
                    record.message = message
                    message = self.formatter.formatMessage(record)
            message_renderable = self.render_message(record, message)
            log_renderable = self.render(
                record=record,
                traceback=None,
                message_renderable=message_renderable,
            )
            self.console.print(log_renderable, end=getattr(record, "end", "\n"))
        except Exception:
            self.handleError(record)


class CustomHandler(Handler):
    """Console handler for logurich's standard and serialized outputs."""

    def __init__(self, renderer: LogurichRenderer, *, serialize: bool = False) -> None:
        super().__init__()
        self.renderer = renderer
        self.highlighter = ReprHighlighter()
        self.serialize = serialize
        self._console: Console = rich_get_console()

    def _should_highlight(self, record: LogRecord) -> bool:
        return bool(getattr(record, "rich_highlight", False)) or bool(
            logger_state.get("rich_highlight")
        )

    def emit(self, record: LogRecord) -> None:
        end = getattr(record, "end", "\n")
        try:
            if self.serialize:
                payload = self.renderer.format_json(record)
                self._console.out(payload, highlight=False, end="\n")
                return

            prefix = self.renderer.build_prefix(record)
            list_context = self.renderer.build_context(record, is_rich_handler=False)
            renderables = self.renderer._renderables(record)
            exception_text = getattr(record, "formatted_exception", "").rstrip("\n")
            stack_text = getattr(record, "formatted_stack", "").rstrip("\n")

            if record.getMessage():
                output_text = _safe_text_from_markup(prefix)
                if list_context:
                    output_text.append_text(
                        _safe_text_from_markup("".join(list_context) + " ")
                    )
                message_text = _safe_text_from_markup(record.getMessage())
                if self._should_highlight(record):
                    message_text = self.highlighter(message_text)
                output_text.append_text(message_text)
                if stack_text:
                    output_text.append("\n")
                    output_text.append_text(Text(stack_text))
                if exception_text:
                    output_text.append("\n")
                    output_text.append_text(Text(exception_text))
                self._console.print(
                    output_text,
                    end=end,
                    highlight=False,
                    soft_wrap=True,
                )
            elif stack_text or exception_text:
                diagnostic = "\n".join(
                    part for part in (stack_text, exception_text) if part
                )
                self._console.print(Text(diagnostic), end=end, highlight=False)

            if renderables:
                rendered = rich_console_renderer(
                    prefix,
                    getattr(record, "render_prefix", True),
                    renderables,
                    getattr(record, "render_width", None),
                )
                self._console.print(*rendered, end=end, highlight=False)
        except Exception:
            self.handleError(record)
