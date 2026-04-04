import os

from rich.panel import Panel
from rich.table import Table

from logurich import ctx, global_context_configure, init_logger, logger


def build_table() -> Table:
    table = Table(title="Serialized Metrics")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("items", "3")
    table.add_row("status", "ok")
    return table


if __name__ == "__main__":
    os.environ["LOGURICH_SERIALIZE"] = "1"
    os.environ["LOGURICH_EXTRA_APP"] = "serialize-demo"

    init_logger(
        "INFO",
        enqueue=False,
        log_filename="serialize-demo.log",
        rotation=None,
        retention=None,
    )

    logger.info(
        "Basic serialized message",
        extra={
            "user": "alice",
            "action": "test",
            "items": [1, 2, 3],
            "nested": {"key": "value"},
        },
    )

    with global_context_configure(request_id=ctx("req-42", show_key=True)):
        logger.info("Message with scoped context")

    logger.rich(
        "INFO",
        Panel("Panel content", border_style="green"),
        build_table(),
        title="Rich payload",
        width=72,
    )

    try:
        raise RuntimeError("serialize example failure")
    except RuntimeError:
        logger.exception("Exception payload")
