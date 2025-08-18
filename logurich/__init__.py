__version__ = "0.1.0"

from .core import global_configure, global_set_context, init_logger, logger, mp_configure

init_logger("INFO")

__all__ = [
    "logger",
    "init_logger",
    "mp_configure",
    "global_configure",
    "global_set_context",
]
