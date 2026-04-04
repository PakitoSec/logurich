import pytest

click = pytest.importorskip("click")
from click.testing import CliRunner  # noqa: E402

from logurich import shutdown_logger  # noqa: E402
from logurich.opt_click import click_logger_init, click_logger_params  # noqa: E402
from logurich.struct import logger_state  # noqa: E402


def test_click_logger_init_registers_atexit_shutdown(monkeypatch):
    registered: list[object] = []

    monkeypatch.setitem(logger_state, "atexit_registered", False)
    monkeypatch.setattr("logurich.core.atexit.register", registered.append)

    click_logger_init("INFO", 0, None, (), False)
    shutdown_logger()

    assert registered.count(shutdown_logger) == 1


def test_click_logger_params_registers_context_shutdown(monkeypatch):
    shutdown_calls: list[str] = []

    monkeypatch.setattr("logurich.opt_click.init_logger", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "logurich.opt_click.shutdown_logger", lambda: shutdown_calls.append("called")
    )

    @click.command()
    @click_logger_params
    def cli() -> None:
        return None

    result = CliRunner().invoke(cli, [])

    assert result.exit_code == 0
    assert shutdown_calls == ["called"]
