import random
import re
import string

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


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}],
    indirect=True,
)
def test_rich_width_affects_output(logger, buffer):
    """Test that different width values produce different output layouts."""
    wide_text = " ".join(["wrap"] * 60)

    # First call with narrow width
    logger.rich("INFO", wide_text, width=60)
    narrow_output = buffer.getvalue()

    # Clear buffer and call with wide width
    buffer.truncate(0)
    buffer.seek(0)
    logger.rich("INFO", wide_text, width=110)
    wide_output = buffer.getvalue()

    narrow_max = len(narrow_output)
    wide_max = len(wide_output)

    assert narrow_max > 0
    assert wide_max > 0
    assert narrow_max < wide_max
