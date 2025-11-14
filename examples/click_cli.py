import click

from logurich import logger
from logurich.opt_click import click_logger_params


@click.command()
@click_logger_params
@click.option("--name", default="Logurich user", help="Name to greet.")
@click.option("--count", default=1, type=int, help="Number of greetings to emit.")
def main(name: str, count: int) -> None:
    """Demonstrate automatic logger wiring inside a Click command."""

    for _ in range(count):
        logger.info("Hello {}", name)

    logger.success("Completed {} greetings", count)


if __name__ == "__main__":
    main()
