"""Structured JSON serialisation of Rich renderables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from rich.align import Align
from rich.columns import Columns
from rich.console import ConsoleRenderable, Group
from rich.constrain import Constrain
from rich.layout import Layout
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .console import rich_to_str

SCHEMA_VERSION = 1

MAX_DEPTH = 4
MAX_TABLE_ROWS = 100

_UNSET = object()
_MARKDOWN: Any = _UNSET
_PLACEHOLDER: Any = _UNSET


@dataclass(frozen=True)
class _Options:
    """Serialisation settings threaded through the recursive walk."""

    max_depth: int = MAX_DEPTH
    max_rows: Optional[int] = MAX_TABLE_ROWS
    styles: bool = False


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


def _placeholder_type() -> Optional[type]:
    """Return the private filler Rich puts in an empty ``Layout``, if present."""

    global _PLACEHOLDER
    if _PLACEHOLDER is _UNSET:
        try:
            from rich.layout import _Placeholder
        except Exception:
            _PLACEHOLDER = None
        else:
            _PLACEHOLDER = _Placeholder
    return _PLACEHOLDER


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


def _optional_text(value: Any, opts: _Options) -> Any:
    return None if value is None else _text_value(value, opts)


def _style_text(value: Any) -> Optional[str]:
    """Normalise a style to its Rich definition string."""

    if value is None or value == "":
        return None
    try:
        return str(value)
    except Exception:
        return None


def _as_text(value: Any) -> Optional[Text]:
    """Return ``value`` as :class:`Text` when it carries recoverable styling."""

    if isinstance(value, Text):
        return value
    if isinstance(value, str):
        try:
            return Text.from_markup(value)
        except Exception:
            return Text(value)
    return None


def _spans(text: Text) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for span in text.spans:
        style = span.style
        if not style:
            continue
        parsed: Optional[Style]
        if isinstance(style, Style):
            parsed = style
        else:
            try:
                parsed = Style.parse(str(style))
            except Exception:
                parsed = None
        definition = _style_text(parsed if parsed is not None else style)
        if definition is None:
            continue
        payload: dict[str, Any] = {
            "start": span.start,
            "end": span.end,
            "style": definition,
        }
        link = getattr(parsed, "link", None)
        if link:
            payload["link"] = link
        spans.append(payload)
    return spans


def _text_payload(value: Any, opts: _Options) -> dict[str, Any]:
    if not opts.styles:
        return {"type": "text", "text": _cell_text(value)}
    text = _as_text(value)
    if text is None:
        return {"type": "text", "text": _cell_text(value)}
    payload: dict[str, Any] = {"type": "text", "text": text.plain}
    spans = _spans(text)
    if spans:
        payload["spans"] = spans
    return payload


def _text_value(value: Any, opts: _Options) -> Any:
    """Plain string in the default mode, structured payload in fidelity mode."""

    if not opts.styles:
        return _cell_text(value)
    return _text_payload(value, opts)


def _lexer_name(syntax: Syntax) -> Optional[str]:
    lexer = getattr(syntax, "_lexer", None)
    if isinstance(lexer, str):
        return lexer
    return getattr(lexer, "name", None)


def _serialize_columns(table: Table, opts: _Options) -> list[Any]:
    if not opts.styles:
        return [_cell_text(column.header) for column in table.columns]
    return [
        {
            "header": _text_value(column.header, opts),
            "justify": column.justify,
            "no_wrap": column.no_wrap,
            "style": _style_text(column.style),
        }
        for column in table.columns
    ]


def _serialize_table(table: Table, opts: _Options) -> dict[str, Any]:
    cells = [list(column.cells) for column in table.columns]
    limit = (
        table.row_count
        if opts.max_rows is None
        else min(table.row_count, opts.max_rows)
    )
    rows = [
        [column[index] if index < len(column) else "" for column in cells]
        for index in range(limit)
    ]
    data: dict[str, Any] = {
        "type": "table",
        "title": _optional_text(table.title, opts),
        "columns": _serialize_columns(table, opts),
        "rows": [[_text_value(cell, opts) for cell in row] for row in rows],
    }
    if opts.styles:
        data["show_header"] = table.show_header
        data["expand"] = table.expand
    if table.row_count > limit:
        data["truncated"] = True
    return data


def _serialize_tree(tree: Tree, depth: int, opts: _Options) -> dict[str, Any]:
    return {
        "type": "tree",
        "label": _text_value(tree.label, opts),
        "children": [_serialize(child, depth + 1, opts) for child in tree.children],
    }


def _serialize_layout(layout: Layout, depth: int, opts: _Options) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": "layout",
        "name": layout.name,
        "direction": getattr(layout.splitter, "name", None),
        "visible": layout.visible,
        "size": layout.size,
        "ratio": layout.ratio,
    }
    children = list(layout.children)
    if children:
        data["children"] = [_serialize(child, depth + 1, opts) for child in children]
        return data
    renderable = layout.renderable
    placeholder = _placeholder_type()
    empty = renderable is layout or (
        placeholder is not None and isinstance(renderable, placeholder)
    )
    data["content"] = None if empty else _serialize(renderable, depth + 1, opts)
    return data


def _serialize_panel(item: Panel, depth: int, opts: _Options) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": "panel",
        "title": _optional_text(item.title, opts),
        "subtitle": _optional_text(item.subtitle, opts),
        "content": _serialize(item.renderable, depth + 1, opts),
    }
    if opts.styles:
        data["border_style"] = _style_text(item.border_style)
        data["title_align"] = item.title_align
        data["subtitle_align"] = item.subtitle_align
    return data


def _serialize_rule(item: Rule, opts: _Options) -> dict[str, Any]:
    data: dict[str, Any] = {"type": "rule", "title": _text_value(item.title, opts)}
    if opts.styles:
        data["align"] = item.align
        data["style"] = _style_text(item.style)
    return data


def _serialize(item: Any, depth: int, opts: _Options) -> dict[str, Any]:
    if depth > opts.max_depth:
        return {"type": "text", "text": _rendered_text(item), "truncated": True}
    if isinstance(item, (str, Text)):
        return _text_payload(item, opts)
    if isinstance(item, Table):
        return _serialize_table(item, opts)
    if isinstance(item, Panel):
        return _serialize_panel(item, depth, opts)
    if isinstance(item, Tree):
        return _serialize_tree(item, depth, opts)
    if isinstance(item, Syntax):
        return {"type": "syntax", "lexer": _lexer_name(item), "code": item.code}
    if isinstance(item, Rule):
        return _serialize_rule(item, opts)
    if isinstance(item, Layout):
        return _serialize_layout(item, depth, opts)
    markdown = _markdown_type()
    if markdown is not None and isinstance(item, markdown):
        return {"type": "markdown", "markup": item.markup}
    if isinstance(item, (Group, Columns)):
        return {
            "type": "group",
            "items": [_serialize(child, depth + 1, opts) for child in item.renderables],
        }
    # Transparent wrappers only carry layout, so they keep the child's depth.
    if isinstance(item, (Padding, Align, Constrain)):
        return _serialize(item.renderable, depth, opts)
    if isinstance(item, ConsoleRenderable):
        return {"type": "text", "text": _rendered_text(item)}
    return {"type": "object", "repr": repr(item)}


def serialize_renderables(
    renderables: tuple[Any, ...],
    *,
    max_depth: int = MAX_DEPTH,
    max_rows: Optional[int] = MAX_TABLE_ROWS,
    styles: bool = False,
) -> list[dict[str, Any]]:
    """Convert Rich renderables into JSON-friendly structured payloads.

    Args:
        renderables (tuple[Any, ...]): Rich renderables to serialise.
        max_depth (int): Recursion limit before falling back to rendered text.
        max_rows (Optional[int]): Table row cap, or ``None`` to keep every row.
        styles (bool): Emit styles, links and layout metadata. Text values then
            become ``{"text": ..., "spans": [...]}`` objects instead of strings.

    Return:
        A list of JSON-serialisable payloads, one per renderable.
    """

    opts = _Options(max_depth=max_depth, max_rows=max_rows, styles=styles)
    return [_serialize(item, 0, opts) for item in renderables]
