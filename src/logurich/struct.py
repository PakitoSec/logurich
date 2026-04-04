"""Shared logger configuration state."""

from typing import Any

logger_state: dict[str, Any] = {
    "min_level": None,
    "level_by_module": None,
    "rich_highlight": False,
    "queue": None,
    "listener": None,
    "final_handlers": (),
    "env_extra": {},
    "atexit_registered": False,
    "threading_atexit_registered": False,
}
