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

    click_logger_init("INFO", 0, None, (), "plain")
    shutdown_logger()

    assert registered.count(shutdown_logger) == 1


def test_click_logger_params_registers_context_shutdown(monkeypatch):
    shutdown_calls: list[str] = []
    init_calls: list[dict[str, object]] = []

    def fake_init(*args, **kwargs):
        init_calls.append(kwargs)

    monkeypatch.setattr("logurich.opt_click.init_logger", fake_init)
    monkeypatch.setattr(
        "logurich.opt_click.shutdown_logger", lambda: shutdown_calls.append("called")
    )

    @click.command()
    @click_logger_params
    def cli() -> None:
        return None

    result = CliRunner().invoke(cli, ["--logger-console", "RICH"])

    assert result.exit_code == 0
    assert init_calls[0]["console"] == "rich"
    assert shutdown_calls == ["called"]


def test_click_console_default_is_plain(monkeypatch):
    received: list[str] = []

    def fake_init(*args, **kwargs):
        received.append(kwargs["console"])

    monkeypatch.setattr("logurich.opt_click.init_logger", fake_init)

    @click.command()
    @click_logger_params
    def cli() -> None:
        return None

    result = CliRunner().invoke(cli, [])
    assert result.exit_code == 0
    assert received == ["plain"]


def test_click_console_help_documents_environment_precedence(monkeypatch):
    monkeypatch.setattr("logurich.opt_click.init_logger", lambda *args, **kwargs: None)

    @click.command()
    @click_logger_params
    def cli() -> None:
        return None

    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    normalized_help = " ".join(result.output.split())
    assert "LOGURICH_OUTPUT takes precedence" in normalized_help


@pytest.mark.parametrize("value", ["auto", "rich", "plain", "json", "RICH"])
def test_click_console_accepts_public_choices(monkeypatch, value):
    monkeypatch.setattr("logurich.opt_click.init_logger", lambda *args, **kwargs: None)

    @click.command()
    @click_logger_params
    def cli() -> None:
        return None

    assert CliRunner().invoke(cli, ["--logger-console", value]).exit_code == 0


def test_click_rejects_invalid_and_removed_options(monkeypatch):
    monkeypatch.setattr("logurich.opt_click.init_logger", lambda *args, **kwargs: None)

    @click.command()
    @click_logger_params
    def cli() -> None:
        return None

    runner = CliRunner()
    assert runner.invoke(cli, ["--logger-console", "invalid"]).exit_code == 2
    removed = runner.invoke(cli, ["--logger-rich"])
    assert removed.exit_code == 2
    assert "No such option" in removed.output
