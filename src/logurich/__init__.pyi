from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import Any, Final, Optional, Union

from rich.console import Console

from .core import LogLevel, LoguRich

LevelByModuleValue = Union[str, int, bool]
LevelByModuleMapping = Mapping[Optional[str], LevelByModuleValue]

__version__: Final[str]

logger: LoguRich
console: Console
LOG_LEVEL_CHOICES: Final[tuple[str, ...]]

def init_logger(
    log_level: LogLevel,
    log_verbose: int = 0,
    log_filename: Optional[str] = None,
    log_folder: str = "logs",
    level_by_module: Optional[LevelByModuleMapping] = None,
    *,
    rich_handler: bool = False,
    diagnose: bool = False,
    enqueue: bool = True,
    highlight: bool = False,
    rotation: Optional[Union[str, int]] = "12:00",
    retention: Optional[Union[str, int]] = "10 days",
) -> Optional[str]: ...
def global_context_configure(**kwargs: Any) -> AbstractContextManager[None]: ...
def global_context_set(**kwargs: Any) -> None: ...
def propagate_loguru_to_std_logger() -> None: ...
def rich_configure_console(*args: object, **kwargs: object) -> Console: ...
def rich_get_console() -> Console: ...
def rich_set_console(console: Console) -> None: ...
def rich_to_str(*objects: object, ansi: bool = True, **kwargs: object) -> str: ...

__all__: Final[list[str]]
