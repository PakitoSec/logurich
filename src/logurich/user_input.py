"""User input utilities with Rich-enhanced prompts and timeout support."""

from __future__ import annotations

import getpass
import logging
import platform
import signal
import sys
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, Union

from rich.console import ConsoleRenderable

logger = logging.getLogger(__name__)


class InputValueError(Exception):
    """Raised when a user-supplied value fails type conversion."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _convert_type(type_: Any, default: Any = None) -> Callable[[str], Any]:
    """Return a callable that converts a string value to *type_*.

    When *type_* is ``None`` the converter is inferred from *default*'s type.
    If both are ``None`` the value is returned as-is (``str``).
    """
    if type_ is None:
        if default is not None:
            type_ = builtins_type(default)
        else:
            return str

    def _proc(value: str) -> Any:
        try:
            return type_(value)
        except (ValueError, TypeError) as exc:
            raise InputValueError(
                f"{value!r} is not a valid {getattr(type_, '__name__', type_)}"
            ) from exc

    return _proc


builtins_type = type  # keep a reference before the parameter shadows it


def user_input(
    text: str,
    prompt_suffix=": ",
    default: Any = None,
    type: Any = None,
    value_proc: Callable[[str], Any] = None,
    custom_logger: Any = None,
    hide_input: bool = False,
    context: Union[str, ConsoleRenderable] = None,
):
    use_logger = logger
    if custom_logger is not None:
        use_logger = custom_logger
    str_default = ""
    if default:
        str_default = f" [default={default}]"
    if value_proc is None:
        value_proc = _convert_type(type, default)
    if context:
        use_logger.rich("INFO", context, prefix=False)
    while True:
        while True:
            use_logger.bind(end="").rich(
                "INFO",
                f"{text}{str_default}{prompt_suffix}",
                prefix=False,
            )
            value = getpass.getpass("") if hide_input is True else input()
            if value:
                break
            elif default is not None:
                value = default
                break
        try:
            result = value_proc(value)
        except InputValueError as e:
            if hide_input:
                use_logger.rich(
                    "ERROR",
                    "Error: The value you entered was invalid",
                    prefix=False,
                )
            else:
                use_logger.rich(
                    "ERROR",
                    f"Error: {e.message}",
                    prefix=False,
                )
            continue
        return result


def raise_timeout(signum, frame):
    logger.error("User input timeout ! Exiting...")
    sys.exit(1)


@contextmanager
def timeout(time):
    signal.signal(signal.SIGALRM, raise_timeout)
    signal.alarm(time)
    try:
        yield
    except TimeoutError:
        pass
    finally:
        signal.signal(signal.SIGALRM, signal.SIG_IGN)


def user_input_with_timeout(msg: str, timeout_duration: int):
    data = None
    if platform.system() == "Windows":
        data = user_input(msg, type=str)
        return data
    else:
        with timeout(timeout_duration):
            data = user_input(msg, type=str)
            return data
