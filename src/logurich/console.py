"""Rich console helpers for logurich rendering."""

from __future__ import annotations

from typing import Any, Optional

from rich.console import Console, ConsoleRenderable
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text

_console: Optional[Console] = None


def rich_to_str(
    *objects: Any, ansi: bool = True, width: Optional[int] = None, **kwargs: Any
) -> str:
    console = rich_get_console()
    if width is not None and width < 1:
        raise ValueError("width must be >= 1")
    print_kwargs = dict(kwargs)
    if width is not None:
        print_kwargs["width"] = width
        print_kwargs["no_wrap"] = True
        print_kwargs["overflow"] = "ellipsis"
    with console.capture() as capture:
        console.print(*objects, **print_kwargs)
    output = capture.get()
    if ansi:
        return output
    return Text.from_ansi(output).plain


def rich_format_grid(
    text_rich_prefix: Text, data: ConsoleRenderable, content_width: Optional[int]
) -> Table:
    grid = Table.grid()
    grid.add_column(no_wrap=True)
    grid.add_column(no_wrap=True)
    content = Text.from_ansi(rich_to_str(data, width=content_width, end=""))
    lines = content.split()
    for line in lines:
        grid.add_row(text_rich_prefix.copy(), line)
    return grid


def _render_rich_item(
    item: Any,
    text_rich_prefix: Text,
    available_width: int,
    effective_width: int,
) -> ConsoleRenderable:
    """Render a single item with rich markup formatting."""
    if isinstance(item, str):
        content = Text.from_markup(item)
        if available_width != effective_width:
            return rich_format_grid(text_rich_prefix, content, effective_width)
        return text_rich_prefix.copy().append(content)

    if isinstance(item, ConsoleRenderable):
        return rich_format_grid(text_rich_prefix, item, effective_width)

    return rich_format_grid(
        text_rich_prefix,
        Pretty(item, max_depth=2, max_length=2),
        effective_width,
    )


def _render_plain_item(
    item: Any,
    effective_width: int,
    content_width: Optional[int],
) -> ConsoleRenderable:
    """Render a single item without rich markup formatting."""
    if isinstance(item, str):
        return Text.from_ansi(item)

    if content_width is not None:
        rendered = rich_to_str(item, width=effective_width, end="")
        return Text.from_ansi(rendered)

    return item


def rich_console_renderer(
    prefix: str, rich_format: bool, data: Any, content_width: Optional[int] = None
) -> list[ConsoleRenderable]:
    console = rich_get_console()
    rich_prefix = prefix[:-2] + "# "
    text_rich_prefix = Text.from_markup(rich_prefix)
    available_width = max(1, console.width - len(text_rich_prefix))
    effective_width = (
        min(available_width, content_width)
        if content_width is not None
        else available_width
    )

    if rich_format:
        return [
            _render_rich_item(r, text_rich_prefix, available_width, effective_width)
            for r in data
        ]
    return [_render_plain_item(r, effective_width, content_width) for r in data]


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
