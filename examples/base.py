from rich.panel import Panel

from logurich import global_configure, init_logger, logger

logger.info("This is a basic log message")

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
    with global_configure(context__app="example"):
        logger.debug("This log has app context")

    # Log with additional context
    logger.bind(context__y_qsd="demo").info("This log has module context")

    # Log an exception
    try:
        1 / 0
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
        Panel("test 2", border_style="green"),
        title="Rich Panel",
        prefix=False,
    )
