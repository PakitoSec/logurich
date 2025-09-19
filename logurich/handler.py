import os
from datetime import datetime
from logging import Handler, LogRecord
from pathlib import Path

from rich.console import ConsoleRenderable
from rich.highlighter import ReprHighlighter
from rich.logging import RichHandler
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text

from .struct import extra_logger

from .console import rich_console_renderer, get_console


class CustomRichHandler(RichHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, console=get_console(), **kwargs)
        self._padding = 10

    def emit(self, record):
        super().emit(record)

    def build_content(self, record: LogRecord, content):
        row = []
        list_context = record.extra.get("_build_list_context", [])
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

    def render(self, *, record: LogRecord, traceback, message_renderable):
        path = Path(record.pathname).name
        level = self.get_level_text(record)
        time_format = None if self.formatter is None else self.formatter.datefmt
        log_time = datetime.fromtimestamp(record.created)
        rich_tb = record.extra.get("rich_traceback")
        rich_console = record.extra.get("rich_console")
        renderables = []
        if rich_console:
            if record.msg:
                renderables.append(self.build_content(record, message_renderable))
            for a in rich_console:
                if isinstance(a, (ConsoleRenderable, str)):
                    renderables.append(a)
                else:
                    renderables.append(Pretty(a))
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.highlighter = ReprHighlighter()
        self.serialize = os.environ.get("LOGURU_SERIALIZE")

    def emit(self, record):
        console = get_console()
        end = record.extra.get("end", "\n")
        if self.serialize:
            console.out(record.msg, highlight=False, end="")
            return
        prefix = record.extra["_prefix"]
        list_context = record.extra.get("_build_list_context", [])
        rich_console = record.extra.get("rich_console")
        rich_format = record.extra.get("rich_format")
        rich_highlight = record.extra.get("rich_highlight")
        conf_rich_highlight = extra_logger.get("conf_rich_highlight")
        try:
            if record.msg:
                p = Text.from_markup(prefix)
                t = p.copy()
                if list_context:
                    t.append_text(Text.from_markup("".join(list_context)) + " ")
                m = Text.from_markup(record.msg)
                if rich_highlight is True or conf_rich_highlight is True:
                    m = self.highlighter(m)
                t.append_text(m)
                console.print(t, end=end, highlight=False)
            if rich_console:
                renderable = rich_console_renderer(prefix, rich_format, rich_console)
                console.print(*renderable, end=end, highlight=False)
        except Exception:
            self.handleError(record)
