import pytest

click = pytest.importorskip("click")

from logurich import shutdown_logger  # noqa: E402
from logurich.opt_click import click_logger_init  # noqa: E402
from logurich.struct import logger_state  # noqa: E402


def test_click_logger_init_registers_atexit_shutdown(monkeypatch):
    registered: list[object] = []

    monkeypatch.setitem(logger_state, "atexit_registered", False)
    monkeypatch.setattr("logurich.core.atexit.register", registered.append)

    click_logger_init("INFO", 0, None, (), False)
    shutdown_logger()

    assert registered == [shutdown_logger]
