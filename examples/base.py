from rich.panel import Panel
from rich.table import Table

from logurich import ctx, init_logger, logger, shutdown_logger


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

    with logger.contextualize(app=logger.ctx("example", style="yellow")):
        logger.info("This log has app context")

    logger.info(
        "This log has per-call context",
        extra={"context": {"session": ctx("sess-42", style="cyan", show_key=True)}},
    )

    try:
        raise ZeroDivisionError("demo")
    except ZeroDivisionError:
        logger.exception("An error occurred while processing %s", "demo")

    # ── bind() ── per-instance context ──────────────────────────────
    api_logger = logger.bind(
        ctx_module=logger.ctx("API", style="magenta"),
    )
    api_logger.info("Request received")
    api_logger.info("Processing complete")

    # Chained bind
    req_logger = api_logger.bind(
        request_id=ctx("req-99", style="cyan", show_key=True),
    )
    req_logger.info("Handling request")

    shutdown_logger()
