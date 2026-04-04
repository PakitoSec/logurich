"""Custom logging handlers for logurich."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from logging import Formatter, Handler, LogRecord
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, Union

from rich.console import ConsoleRenderable
from rich.highlighter import ReprHighlighter
from rich.logging import RichHandler
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text

from .console import rich_console_renderer, rich_get_console, rich_to_str
from .struct import logger_state

if TYPE_CHECKING:
    from rich.console import Console, RenderableType

DEFAULT_CONTENT_PADDING = (0, 10, 22, 25)
SERIALIZATION_START = perf_counter()


def _safe_text_from_markup(value: str) -> Text:
    try:
        return Text.from_markup(value)
    except Exception:
        return Text(value)


def _context_display_name(name: str) -> str:
    if name.startswith("context::"):
        return name.split("::", 1)[1]
    return name


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
            display_name = _context_display_name(name)
            if hasattr(value, "render"):
                list_context.append(
                    value.render(display_name, is_rich_handler=is_rich_handler)
                )
            else:
                list_context.append(f"[{display_name}={value}]")
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

    def format_file(self, record: LogRecord) -> str:
        prefix_markup = self.build_prefix(record)
        prefix_plain = _safe_text_from_markup(prefix_markup).plain
        context_markup = "".join(self.build_context(record, is_rich_handler=False))
        context_plain = _safe_text_from_markup(
            context_markup + (" " if context_markup else "")
        ).plain
        message_plain = _safe_text_from_markup(record.getMessage()).plain
        exception_text = getattr(record, "formatted_exception", "").rstrip("\n")

        parts: list[str] = []
        if message_plain or not self._renderables(record):
            line = f"{prefix_plain}{context_plain}{message_plain}"
            if exception_text:
                line = f"{line}\n{exception_text}" if line else exception_text
            parts.append(line)

        renderables = self._renderables(record)
        if renderables:
            rendered = rich_console_renderer(
                prefix_markup,
                getattr(record, "render_prefix", True),
                renderables,
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
        text = self.format_file(record)
        end = getattr(record, "end", "\n")
        rendered_text = f"{text}{end}" if text else ""
        extra = self._serialize_extra(record)
        created_at = datetime.fromtimestamp(record.created).astimezone()
        exception_data = getattr(record, "exception_data", None)
        file_path = str(Path(record.pathname))
        elapsed_seconds = perf_counter() - SERIALIZATION_START
        renderables = self._renderables(record)
        message_value = record.getMessage()
        if renderables and text:
            lines = text.splitlines()
            continuation = "\n".join(lines[1:])
            if continuation:
                message_value = f"{message_value}\n{continuation}"
        payload = {
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
        return json.dumps(payload, default=str, ensure_ascii=False)

    def _serialize_extra(self, record: LogRecord) -> dict[str, Any]:
        context = getattr(record, "context", {}) or {}
        serialized = dict(logger_state.get("env_extra", {}))
        serialized.update(
            {
                _context_display_name(key): getattr(value, "value", value)
                for key, value in context.items()
            }
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
            return self.renderer.format_json(record)
        return self.renderer.format_file(record)


class CustomRichHandler(RichHandler):
    """Rich-formatted handler using standard log records."""

    def __init__(
        self, renderer: LogurichRenderer, *args: object, **kwargs: object
    ) -> None:
        self.renderer = renderer
        super().__init__(*args, console=rich_get_console(), **kwargs)

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
        output: list[RenderableType] = []

        if record.getMessage():
            output.append(self.build_content(record, message_renderable))
        for item in renderables:
            if isinstance(item, (ConsoleRenderable, str)):
                output.append(item)
            else:
                output.append(Pretty(item))
        if rich_tb is not None:
            output.append(rich_tb)

        return self._log_render(
            self.console,
            output,
            log_time=log_time,
            time_format=time_format,
            level=level,
            path=path,
            line_no=record.lineno,
            link_path=record.pathname if self.enable_link_path else None,
        )


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
                self._console.out(payload, highlight=False, end=end)
                return

            prefix = self.renderer.build_prefix(record)
            list_context = self.renderer.build_context(record, is_rich_handler=False)
            renderables = self.renderer._renderables(record)
            exception_text = getattr(record, "formatted_exception", "").rstrip("\n")

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
                if exception_text:
                    output_text.append("\n")
                    output_text.append_text(Text(exception_text))
                self._console.print(output_text, end=end, highlight=False)
            elif exception_text:
                self._console.print(Text(exception_text), end=end, highlight=False)

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
