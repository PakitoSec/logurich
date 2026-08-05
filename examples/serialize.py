from rich.panel import Panel
from rich.table import Table

from logurich import ctx, get_logger, global_context, init_logger


def build_table() -> Table:
    table = Table(title="Serialized Metrics")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("items", "3")
    table.add_row("status", "ok")
    return table


if __name__ == "__main__":
    init_logger(
        "INFO",
        console="json",
        file="json",
        enqueue=False,
        log_filename="serialize-demo.log",
        rotation=None,
        retention=None,
    )
    logger = get_logger(__name__)

    logger.info(
        "Basic serialized message",
        user="alice",
        action="test",
        items=[1, 2, 3],
        nested={"key": "value"},
    )

    with global_context(request_id=ctx("req-42")):
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
