"""Custom logging handlers for logurich.

Provides two main handler classes:
- CustomRichHandler: Rich-formatted handler using RichHandler as base
- CustomHandler: Lightweight handler for console output without rich tables
"""

from __future__ import annotations

from datetime import datetime
from logging import Handler, LogRecord
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import ConsoleRenderable
from rich.highlighter import ReprHighlighter
from rich.logging import RichHandler
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text

from .console import rich_console_renderer, rich_get_console
from .struct import extra_logger
from .utils import parse_bool_env

if TYPE_CHECKING:
    from rich.console import Console, RenderableType

# Default padding for handler content alignment
# This value represents the initial column width for context prefixes
DEFAULT_CONTENT_PADDING = 10


class CustomRichHandler(RichHandler):
    """Custom Rich handler with enhanced context rendering.

    Extends RichHandler to support logurich's context system and custom formatting.
    Renders log records using Rich's table-based layout with support for nested
    context breadcrumbs and traceback rendering.

    Args:
        *args: Positional arguments passed to RichHandler
        **kwargs: Keyword arguments passed to RichHandler
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, console=rich_get_console(), **kwargs)
        self._padding: int = DEFAULT_CONTENT_PADDING

    def emit(self, record: LogRecord) -> None:
        """Emit a log record using the parent RichHandler.

        Args:
            record: The log record to emit
        """
        super().emit(record)

    def build_content(self, record: LogRecord, content: RenderableType) -> Table:
        """Build a Rich table grid with optional context breadcrumbs.

        Args:
            record: The log record containing extra context data
            content: The renderable message content

        Returns:
            A Rich Table grid with context prefix and message content
        """
        row: list[str | RenderableType] = []
        list_context: list[str] = record.extra.get("_build_list_context", [])
        grid = Table.grid(expand=True)
        if list_context:
            grid.add_column(justify="left", style="bold", vertical="middle")
            str_context = ".".join(list_context)
            row.append(str_context + " :arrow_forward:  ")
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
        """Render a log record as a Rich renderable.

        Args:
            record: The log record to render
            traceback: Optional traceback object
            message_renderable: The rendered message content

        Returns:
            A Rich renderable representing the complete log entry
        """
        path = Path(record.pathname).name
        level = self.get_level_text(record)
        time_format = None if self.formatter is None else self.formatter.datefmt
        log_time = datetime.fromtimestamp(record.created)
        rich_tb = record.extra.get("rich_traceback")
        rich_console = record.extra.get("rich_console")
        renderables: list[RenderableType] = []
        if rich_console:
            if record.msg:
                renderables.append(self.build_content(record, message_renderable))
            for item in rich_console:
                if isinstance(item, (ConsoleRenderable, str)):
                    renderables.append(item)
                else:
                    renderables.append(Pretty(item))
        else:
            renderables.append(self.build_content(record, message_renderable))
        if traceback and rich_tb:
            renderables.append(rich_tb)
        log_renderable = self._log_render(
            self.console,
            renderables,
            log_time=log_time,
            time_format=time_format,
            level=level,
            path=path,
            line_no=record.lineno,
            link_path=record.pathname if self.enable_link_path else None,
        )
        return log_renderable


class CustomHandler(Handler):
    """Lightweight custom handler for console output.

    Handles log formatting without Rich tables, using text-based markup rendering.
    Supports serialization mode for structured output and rich highlighting for
    enhanced readability.

    Args:
        *args: Positional arguments passed to Handler
        **kwargs: Keyword arguments passed to Handler
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.highlighter = ReprHighlighter()
        self.serialize: bool | None = parse_bool_env("LOGURU_SERIALIZE")
        self._console: Console = rich_get_console()

    def _should_highlight(self, record: LogRecord) -> bool:
        """Determine if syntax highlighting should be applied.

        Args:
            record: The log record to check

        Returns:
            True if highlighting should be enabled
        """
        rich_highlight = record.extra.get("rich_highlight")
        conf_rich_highlight = extra_logger.get("__rich_highlight")
        return rich_highlight is True or conf_rich_highlight is True

    def emit(self, record: LogRecord) -> None:
        """Emit a log record to the console.

        Handles both serialized output mode and rich markup rendering mode.
        Applies syntax highlighting based on configuration and formats context
        breadcrumbs when present.

        Args:
            record: The log record to emit
        """
        end: str = record.extra.get("end", "\n")
        if self.serialize:
            self._console.out(record.msg, highlight=False, end="")
            return

        prefix: str = record.extra["_prefix"]
        list_context: list[str] = record.extra.get("_build_list_context", [])
        rich_console = record.extra.get("rich_console")
        rich_format = record.extra.get("rich_format")

        try:
            if record.msg:
                prefix_text = Text.from_markup(prefix)
                output_text = prefix_text.copy()
                if list_context:
                    context_text = Text.from_markup("".join(list_context)) + " "
                    output_text.append_text(context_text)
                message_text = Text.from_markup(record.msg)
                if self._should_highlight(record):
                    message_text = self.highlighter(message_text)
                output_text.append_text(message_text)
                self._console.print(output_text, end=end, highlight=False)
            if rich_console:
                renderable = rich_console_renderer(prefix, rich_format, rich_console)
                self._console.print(*renderable, end=end, highlight=False)
        except Exception:
            self.handleError(record)
