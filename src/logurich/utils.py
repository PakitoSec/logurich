"""Utility helpers for logurich."""

import os


def parse_bool_env(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    return normalized not in {"0", "false", "no", "off", ""}
