from __future__ import annotations

from typing import Any, Literal

from loguru._logger import Logger as _Logger
from rich.console import ConsoleRenderable

class ContextValue:
    value: Any
    value_style: str | None
    bracket_style: str | None
    label: str | None
    show_key: bool

    def __init__(
        self,
        value: Any,
        value_style: str | None = ...,
        bracket_style: str | None = ...,
        label: str | None = ...,
        show_key: bool = ...,
    ) -> None: ...
    def _label(self, key: str) -> str | None: ...
    def render(self, key: str, *, is_rich_handler: bool) -> str: ...

class LoguRich(_Logger):
    @staticmethod
    def ctx(
        value: Any,
        *,
        style: str | None = None,
        value_style: str | None = None,
        bracket_style: str | None = None,
        label: str | None = None,
        show_key: bool | None = None,
    ) -> ContextValue: ...
    @staticmethod
    def level_set(level: LogLevel) -> None: ...
    @staticmethod
    def level_restore() -> None: ...
    @staticmethod
    def configure_child_logger(logger_: LoguRich) -> None: ...
    def rich(
        self,
        log_level: str,
        *renderables: ConsoleRenderable | str,
        title: str = "",
        prefix: bool = True,
        end: str = "\n",
    ) -> None: ...

logger: LoguRich
LogLevel = Literal["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
LOG_LEVEL_CHOICES: tuple[str, ...]
