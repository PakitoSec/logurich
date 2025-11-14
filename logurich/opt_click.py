import functools

import click

from . import LOG_LEVEL_CHOICES, init_logger, logger


LOGGER_PARAM_NAMES = (
    "logger_level",
    "logger_verbose",
    "logger_filename",
    "logger_level_by_module",
    "logger_diagnose",
)


def click_logger_params(func):
    @click.option(
        "-l",
        "--logger-level",
        default="INFO",
        help="Logger level",
        type=click.Choice(LOG_LEVEL_CHOICES, case_sensitive=False),
    )
    @click.option("-v", "--logger-verbose", help="Logger increase verbose", count=True)
    @click.option(
        "--logger-filename",
        help="Logger log filename",
        type=str,
    )
    @click.option(
        "--logger-level-by-module",
        multiple=True,
        help="Logger level by module",
        type=(str, str),
    )
    @click.option(
        "--logger-diagnose",
        is_flag=True,
        help="Logger activate loguru diagnose",
        type=bool,
        default=False,
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        missing = [name for name in LOGGER_PARAM_NAMES if name not in kwargs]
        if missing:
            raise RuntimeError(
                "Logger CLI parameters missing from invocation: {}".format(
                    ", ".join(missing)
                )
            )
        logger_kwargs = {name: kwargs.pop(name) for name in LOGGER_PARAM_NAMES}
        click_logger_init(**logger_kwargs)
        return func(*args, **kwargs)

    return wrapper


def click_logger_init(
    logger_level,
    logger_verbose,
    logger_filename,
    logger_level_by_module,
    logger_diagnose,
):
    lbm = {}
    for mod, level in logger_level_by_module:
        lbm[mod] = level
    log_path = init_logger(
        logger_level,
        logger_verbose,
        log_filename=logger_filename,
        level_by_module=lbm,
        diagnose=logger_diagnose,
    )
    logger.debug("Log level:            {}", logger_level)
    logger.debug("Log verbose:          {}", logger_verbose)
    logger.debug("Log filename:         {}", logger_filename)
    logger.debug("Log path:             {}", log_path)
    logger.debug("Log level by module:  {}", lbm)
    logger.debug("Log diagnose:         {}", logger_diagnose)
