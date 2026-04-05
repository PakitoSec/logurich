import logging

from logurich import init_logger, user_input, user_input_with_timeout

if __name__ == "__main__":
    init_logger("INFO", enqueue=False)
    logger = logging.getLogger(__name__)

    # Basic string input
    name = user_input("Enter your name", type=str)
    logger.info("Hello %s!", name)

    # Integer input with default
    count = user_input("How many items?", type=int, default=5)
    logger.info("Items: %d", count)

    # Hidden input (e.g. passwords)
    secret = user_input("Enter secret", type=str, hide_input=True)
    logger.info("Secret length: %d", len(secret))

    # Custom logger
    custom = logging.getLogger("custom")
    colour = user_input("Favourite colour", type=str, custom_logger=custom)
    logger.info("Colour: %s", colour)

    # Input with timeout (5 seconds, Unix only)
    answer = user_input_with_timeout("Quick! Type something", timeout_duration=5)
    logger.info("You typed: %s", answer)
