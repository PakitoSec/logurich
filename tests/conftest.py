from io import StringIO

import pytest

from logurich import get_logger, init_logger, shutdown_logger
from logurich.console import rich_configure_console


@pytest.fixture
def buffer():
    stream = StringIO()
    rich_configure_console(file=stream, width=120)
    yield stream
    rich_configure_console()


@pytest.fixture
def logger(request):
    default_cfg = {
        "level": "INFO",
        "verbose": 0,
        "enqueue": False,
        "console": "plain",
    }
    cfg = {**default_cfg, **getattr(request, "param", {})}
    init_logger(
        cfg["level"],
        log_verbose=cfg["verbose"],
        enqueue=cfg["enqueue"],
        console=cfg["console"],
    )
    yield get_logger("tests.fixture")
    shutdown_logger()
