"""Context primitives used by Logurich loggers and renderers."""

from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Optional

from rich.markup import escape
from rich.text import Text

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

_context_state: contextvars.ContextVar[Optional[dict[str, ContextValue]]] = (
    contextvars.ContextVar("logurich_context_state", default=None)
)


def normalize_style(style: Optional[str]) -> Optional[str]:
    """Return the canonical Rich style for a public style value."""

    if style is None:
        return None
    style = style.strip()
    if not style:
        return None
    return COLOR_ALIASES.get(style, style)


def _wrap_markup(style: Optional[str], text: str) -> str:
    normalized = normalize_style(style)
    if not normalized:
        return text
    return f"[{normalized}]{text}[/{normalized}]"


@dataclass(frozen=True)
class ContextValue:
    """A context value and its optional Rich display metadata."""

    value: Any
    value_style: Optional[str] = None
    bracket_style: Optional[str] = None
    label: Optional[str] = None
    show_key: bool = True

    def _label(self, key: str) -> Optional[str]:
        if self.label is not None:
            return self.label
        if self.show_key:
            return key
        return None

    def render(self, key: str, *, is_rich_handler: bool) -> str:
        """Render this value as Rich markup for a console handler."""

        label = self._label(key)
        value_text = _wrap_markup(self.value_style, escape(str(self.value)))
        body = f"{escape(label)}={value_text}" if label else value_text
        if is_rich_handler:
            return body
        if normalize_style(self.bracket_style):
            left = _wrap_markup(self.bracket_style, "[")
            right = _wrap_markup(self.bracket_style, "]")
        else:
            left = r"\["
            right = "]"
        return f"{left}{body}{right}"

    def render_text(self, key: str) -> str:
        """Render this value without ANSI codes or Rich markup."""

        return Text.from_markup(self.render(key, is_rich_handler=False)).plain

    def render_json(self) -> Any:
        """Return the style-free value used in JSON output."""

        return self.value


def ctx(
    value: Any,
    *,
    style: Optional[str] = None,
    value_style: Optional[str] = None,
    bracket_style: Optional[str] = None,
    label: Optional[str] = None,
    show_key: Optional[bool] = None,
) -> ContextValue:
    """Build a styled context value.

    Keys are displayed by default, exactly as for raw context values. Pass
    ``show_key=False`` to hide the key, or ``label=`` to rename it.
    """

    effective_value_style = value_style if value_style is not None else style
    return ContextValue(
        value=value,
        value_style=effective_value_style,
        bracket_style=bracket_style,
        label=label,
        show_key=bool(show_key) if show_key is not None else True,
    )


def coerce_context_value(value: Any) -> ContextValue:
    """Normalise a raw user value while preserving explicit ``None`` values."""

    if isinstance(value, ContextValue):
        return value
    return ContextValue(value=value)


def normalize_context(values: Mapping[str, Any]) -> dict[str, ContextValue]:
    """Return a detached, string-keyed context mapping."""

    return {str(key): coerce_context_value(value) for key, value in values.items()}


def get_context() -> dict[str, ContextValue]:
    """Return a copy of the context local to the current execution."""

    current = _context_state.get()
    return dict(current) if current else {}


@contextlib.contextmanager
def global_context(**values: Any) -> Iterator[None]:
    """Temporarily extend the context of the current execution.

    ``ContextVar`` propagation follows Python's normal rules: asyncio tasks
    inherit the current context, while new threads and processes do not do so
    implicitly.
    """

    updated = get_context()
    updated.update(normalize_context(values))
    token = _context_state.set(updated)
    try:
        yield
    finally:
        _context_state.reset(token)


def global_context_set(**values: Any) -> None:
    """Update context for subsequent logs in the current execution."""

    updated = get_context()
    updated.update(normalize_context(values))
    _context_state.set(updated)


def global_context_unset(*keys: str) -> None:
    """Remove context keys from the current execution, ignoring missing keys."""

    updated = get_context()
    for key in keys:
        updated.pop(key, None)
    _context_state.set(updated)


def global_clear_context() -> None:
    """Clear all context in the current execution."""

    _context_state.set({})
