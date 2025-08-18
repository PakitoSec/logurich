from io import StringIO

import pytest

from logurich import (
    init_logger,
)
from logurich import (
    logger as _logger,
)
from logurich.console import configure_console


@pytest.fixture
def buffer():
    buffer = StringIO()
    configure_console(file=buffer, width=120)
    yield buffer


@pytest.fixture
def logger(request):
    default_cfg = {"level": "INFO", "verbose": 0, "enqueue": False}
    cfg = getattr(request, "param", default_cfg)
    for k in default_cfg:
        if k not in cfg:
            cfg[k] = default_cfg[k]
    init_logger(cfg["level"], log_verbose=cfg["verbose"], enqueue=cfg["enqueue"])
    yield _logger
