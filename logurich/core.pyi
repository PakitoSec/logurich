from __future__ import annotations

from typing import Literal

from loguru._logger import Logger as _Logger
from rich.console import ConsoleRenderable

class LoguRich(_Logger):
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
