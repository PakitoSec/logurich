from rich.panel import Panel
from rich.table import Table

from logurich import ctx, global_context_configure, init_logger, logger, shutdown_logger


def create_rich_table() -> Table:
    table = Table(title="Sample Table")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("items", "10")
    table.add_row("status", "ok")
    return table


if __name__ == "__main__":
    init_logger("INFO", enqueue=False)

    logger.info("This is a basic log message")
    logger.info("Hello %s", "world")
    logger.info(
        "Structured output",
        extra={
            "renderables": (
                Panel("Rich panel content", border_style="green"),
                create_rich_table(),
            )
        },
    )

    with global_context_configure(app=ctx("example", style="yellow")):
        logger.info("This log has app context")

    logger.info(
        "This log has per-call context",
        extra={"context": {"session": ctx("sess-42", style="cyan", show_key=True)}},
    )

    try:
        raise ZeroDivisionError("demo")
    except ZeroDivisionError:
        logger.exception("An error occurred while processing %s", "demo")

    shutdown_logger()
