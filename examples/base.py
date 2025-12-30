from rich.panel import Panel
from rich.table import Table

from logurich import global_context_configure, init_logger, logger

logger.info("This is a basic log message")


def create_rich_table():
    table = Table(title="Sample Table")
    columns = [f"Column {i + 1}" for i in range(5)]
    for col in columns:
        table.add_column(col)
    for row in range(10):
        table.add_row(*[f"Row{row + 1}Col{col + 1}" for col in range(5)])
    return table


if __name__ == "__main__":
    logger.info("Example message")
    logger.rich("INFO", "OK")
    logger.rich("INFO", {"fake": "test"})
    logger.rich("INFO", {f"fake{i}": "test" for i in range(10)})
    logger.rich(
        "INFO",
        "[cyan]structure[/cyan]",
        {f"fake{i}": "test" for i in range(10)},
        title="This is the title",
    )
    # Use rich logging
    logger.rich("INFO", "[bold blue]This is a rich formatted log message[/bold blue]")

    # Use context in logging
    with global_context_configure(app=logger.ctx("example", style="yellow")):
        logger.info("This log has app context")

    with logger.contextualize(user=logger.ctx("test", style="cyan", show_key=True)):
        logger.info("ok")

    # Log with additional context
    logger.bind(environment=logger.ctx("demo", style="yellow")).info(
        "This log has module context"
    )

    # Use logger.ctx() directly (no separate import needed)
    logger.bind(session=logger.ctx("sess-42", style="cyan")).info(
        "Using logger.ctx() instead of importing ctx"
    )

    # Temporarily raise the minimum level
    logger.level_set("WARNING")
    logger.info("filtered")
    logger.warning("visible")
    logger.level_restore()

    # Log an exception
    try:
        1 / 0  # noqa: B018
    except Exception as e:
        logger.error("{}", e)
        # logger.exception("An error occurred: {}", e)

    init_logger("DEBUG", log_verbose=3)
    logger.debug("reconfigured")

    # Panel rich objet with logger and prefix
    logger.rich(
        "INFO", Panel("Rich Panel", border_style="green"), title="Rich Panel Object"
    )

    # Panel rich objet without prefix
    logger.rich(
        "INFO",
        Panel("Rich Panel without prefix", border_style="green"),
        title="Rich Panel",
        prefix=False,
    )

    t = create_rich_table()
    logger.rich("INFO", t, title="test")
    logger.rich("INFO", t, title="test", prefix=False)
