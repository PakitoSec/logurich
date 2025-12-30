from __future__ import annotations

from typing import Any, Literal

from loguru._logger import Logger as _Logger
from rich.console import ConsoleRenderable

from .core import ContextValue

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
