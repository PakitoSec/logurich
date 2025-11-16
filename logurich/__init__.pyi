from __future__ import annotations

from typing import ContextManager, Final, Mapping, Protocol

from rich.console import Console

from .core import ContextValue, LogLevel, LoguRich

LevelByModuleValue = str | int | bool
LevelByModuleMapping = Mapping[str | None, LevelByModuleValue]

class _SupportsStr(Protocol):
    def __str__(self) -> str: ...

ContextBinding = ContextValue | _SupportsStr | None

__version__: Final[str]

logger: LoguRich
LOG_LEVEL_CHOICES: Final[tuple[str, ...]]

def ctx(
    value: object,
    *,
    style: str | None = None,
    value_style: str | None = None,
    bracket_style: str | None = None,
    label: str | None = None,
    show_key: bool | None = None,
) -> ContextValue: ...
def init_logger(
    log_level: LogLevel,
    log_verbose: int = 0,
    log_filename: str | None = None,
    log_folder: str = "logs",
    level_by_module: LevelByModuleMapping | None = None,
    *,
    rich_handler: bool = False,
    diagnose: bool = False,
    enqueue: bool = True,
    highlight: bool = False,
) -> str | None: ...
def mp_configure(logger_: LoguRich) -> None: ...
def global_configure(**kwargs: ContextBinding) -> ContextManager[None]: ...
def global_set_context(**kwargs: ContextBinding) -> None: ...
def configure_console(*args: object, **kwargs: object) -> Console: ...
def get_console() -> Console: ...
def set_console(console: Console) -> None: ...
def rich_to_str(*objects: object, ansi: bool = True, **kwargs: object) -> str: ...

__all__: Final[list[str]]
