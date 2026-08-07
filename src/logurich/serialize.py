"""Structured JSON serialisation of Rich renderables."""

from __future__ import annotations

from typing import Any, Optional

from rich.align import Align
from rich.columns import Columns
from rich.console import ConsoleRenderable, Group
from rich.constrain import Constrain
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .console import rich_to_str

MAX_DEPTH = 4
MAX_TABLE_ROWS = 100

_UNSET = object()
_MARKDOWN: Any = _UNSET


def _markdown_type() -> Optional[type]:
    """Return ``rich.markdown.Markdown`` lazily, or ``None`` when unavailable."""

    global _MARKDOWN
    if _MARKDOWN is _UNSET:
        try:
            from rich.markdown import Markdown
        except Exception:
            _MARKDOWN = None
        else:
            _MARKDOWN = Markdown
    return _MARKDOWN


def _plain(value: str) -> str:
    try:
        return Text.from_markup(value).plain
    except Exception:
        return value


def _rendered_text(item: Any) -> str:
    try:
        return rich_to_str(item, ansi=False, end="").rstrip("\n")
    except Exception:
        return str(item)


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Text):
        return value.plain
    if isinstance(value, str):
        return _plain(value)
    return _rendered_text(value)


def _optional_text(value: Any) -> Optional[str]:
    return None if value is None else _cell_text(value)


def _lexer_name(syntax: Syntax) -> Optional[str]:
    lexer = getattr(syntax, "_lexer", None)
    if isinstance(lexer, str):
        return lexer
    return getattr(lexer, "name", None)


def _serialize_table(table: Table) -> dict[str, Any]:
    cells = [list(column.cells) for column in table.columns]
    limit = min(table.row_count, MAX_TABLE_ROWS)
    rows = [
        [column[index] if index < len(column) else "" for column in cells]
        for index in range(limit)
    ]
    data: dict[str, Any] = {
        "type": "table",
        "title": _optional_text(table.title),
        "columns": [_cell_text(column.header) for column in table.columns],
        "rows": [[_cell_text(cell) for cell in row] for row in rows],
    }
    if table.row_count > limit:
        data["truncated"] = True
    return data


def _serialize_tree(tree: Tree, depth: int) -> dict[str, Any]:
    return {
        "type": "tree",
        "label": _cell_text(tree.label),
        "children": [_serialize(child, depth + 1) for child in tree.children],
    }


def _serialize(item: Any, depth: int) -> dict[str, Any]:
    if depth > MAX_DEPTH:
        return {"type": "text", "text": _rendered_text(item), "truncated": True}
    if isinstance(item, str):
        return {"type": "text", "text": _plain(item)}
    if isinstance(item, Text):
        return {"type": "text", "text": item.plain}
    if isinstance(item, Table):
        return _serialize_table(item)
    if isinstance(item, Panel):
        return {
            "type": "panel",
            "title": _optional_text(item.title),
            "subtitle": _optional_text(item.subtitle),
            "content": _serialize(item.renderable, depth + 1),
        }
    if isinstance(item, Tree):
        return _serialize_tree(item, depth)
    if isinstance(item, Syntax):
        return {"type": "syntax", "lexer": _lexer_name(item), "code": item.code}
    if isinstance(item, Rule):
        return {"type": "rule", "title": _cell_text(item.title)}
    markdown = _markdown_type()
    if markdown is not None and isinstance(item, markdown):
        return {"type": "markdown", "markup": item.markup}
    if isinstance(item, (Group, Columns)):
        return {
            "type": "group",
            "items": [_serialize(child, depth + 1) for child in item.renderables],
        }
    # Transparent wrappers only carry layout, so they keep the child's depth.
    if isinstance(item, (Padding, Align, Constrain)):
        return _serialize(item.renderable, depth)
    if isinstance(item, ConsoleRenderable):
        return {"type": "text", "text": _rendered_text(item)}
    return {"type": "object", "repr": repr(item)}


def serialize_renderables(renderables: tuple[Any, ...]) -> list[dict[str, Any]]:
    """Convert Rich renderables into JSON-friendly structured payloads."""

    return [_serialize(item, 0) for item in renderables]
