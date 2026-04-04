from io import StringIO

import pytest

from logurich import init_logger, shutdown_logger
from logurich import logger as _logger
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
        "rich_handler": False,
    }
    cfg = {**default_cfg, **getattr(request, "param", {})}
    init_logger(
        cfg["level"],
        log_verbose=cfg["verbose"],
        enqueue=cfg["enqueue"],
        rich_handler=cfg["rich_handler"],
    )
    yield _logger
    shutdown_logger()
