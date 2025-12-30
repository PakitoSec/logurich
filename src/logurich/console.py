"""Rich console helpers for logurich rendering."""

from __future__ import annotations

from typing import Any

from rich.console import Console, ConsoleRenderable
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text

_console = None


def rich_to_str(*objects, ansi: bool = True, **kwargs) -> str:
    console = rich_get_console()
    with console.capture() as capture:
        console.print(*objects, **kwargs)
    if ansi is True:
        return capture.get()
    return str(Text.from_ansi(capture.get()))


def rich_format_grid(prefix: Text, data: ConsoleRenderable, real_width: int) -> Table:
    grid = Table.grid()
    grid.add_column()
    grid.add_column()
    content = Text.from_ansi(rich_to_str(data, width=real_width, end=""))
    lines = content.split()
    for line in lines:
        pline = prefix.copy()
        grid.add_row(pline, line)
    return grid


def rich_console_renderer(
    prefix: str, rich_format: bool, data: Any
) -> list[ConsoleRenderable]:
    console = rich_get_console()
    rich_prefix = prefix[:-2] + "# "
    pp = Text.from_markup(rich_prefix)
    real_width = console.width - len(pp)
    renderable = []
    for r in data:
        if rich_format:
            if isinstance(r, str):
                item = pp.copy()
                item = item.append(Text.from_markup(r))
                renderable.append(item)
            elif isinstance(r, Text) and len(r.split()) == 1:
                item = pp.copy()
                item = item.append_text(r)
                renderable.append(item)
            elif isinstance(r, ConsoleRenderable):
                renderable.append(rich_format_grid(pp, r, real_width))
            else:
                renderable.append(
                    rich_format_grid(
                        pp, Pretty(r, max_depth=2, max_length=2), real_width
                    )
                )
        else:
            if isinstance(r, str):
                renderable.append(Text.from_ansi(r))
            else:
                renderable.append(r)
    return renderable


def rich_set_console(console: Console) -> None:
    global _console
    if _console is None:
        _console = console
        return
    _console.__dict__ = console.__dict__


def rich_get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(markup=True)
    return _console


def rich_configure_console(*args: Any, **kwargs: Any) -> Console:
    """Reconfigures the logurich console by replacing it with another.

    Args:
        *args (Any): Positional arguments for the replacement :class:`~rich.console.Console`.
        **kwargs (Any): Keyword arguments for the replacement :class:`~rich.console.Console`.

    Return:
        Return the logurich console
    """
    new_console = Console(*args, **kwargs)
    _console = rich_get_console()
    _console.__dict__ = new_console.__dict__
    return _console


console = rich_get_console()
