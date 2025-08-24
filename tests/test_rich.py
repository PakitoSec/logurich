import random
import string
import re
import pytest
from rich.pretty import Pretty


def generate_random_dict(k, depth=3):
    if depth <= 1:
        return {
            "".join(random.choices(string.ascii_letters, k=5)): random.randint(1, 100)
            for _ in range(k)
        }
    else:
        return {
            "".join(random.choices(string.ascii_letters, k=20)): generate_random_dict(
                k, depth - 1
            )
            for _ in range(k)
        }


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}, {"level": "INFO", "enqueue": True}],
    indirect=True,
)
def test_rich(logger, buffer):
    logger.rich(
        "INFO",
        Pretty(generate_random_dict(5, 5), max_length=3, max_depth=3),
    )
    lines = buffer.getvalue().splitlines()
    for line in lines:
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d+ \| INFO", line)
