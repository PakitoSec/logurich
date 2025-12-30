import os

extra_logger = {
    "__min_level": None,
    "__level_upper_only": None,
    "__level_per_module": None,
    "__rich_highlight": False,
}


def _parse_bool_env(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    return normalized not in {"0", "false", "no", "off", ""}
