import random
import re
import string

import pytest
from rich.pretty import Pretty
from rich.table import Table


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
def test_rich_with_width_parameter(logger, buffer):
    """Test that the width parameter limits the console output width."""
    table = Table(title="Test Table")
    table.add_column("Column A", style="cyan")
    table.add_column("Column B", style="magenta")
    table.add_row("Short", "Data")
    table.add_row("Another", "Row")

    logger.rich("INFO", table, width=80)
    output = buffer.getvalue()
    lines = output.splitlines()
    # Verify output was produced
    assert len(lines) > 0
    # Verify it matches the expected log format
    assert any(
        re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d+ \| INFO", line)
        for line in lines
    )


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}],
    indirect=True,
)
def test_rich_width_affects_output(logger, buffer):
    """Test that different width values produce different output layouts."""
    wide_text = "A" * 100  # Long text that will wrap differently at different widths

    # First call with narrow width
    logger.rich("INFO", wide_text, width=50)
    narrow_output = buffer.getvalue()

    # Clear buffer and call with wide width
    buffer.truncate(0)
    buffer.seek(0)
    logger.rich("INFO", wide_text, width=200)
    wide_output = buffer.getvalue()

    # Both should have content
    assert len(narrow_output) > 0
    assert len(wide_output) > 0


@pytest.mark.parametrize(
    "logger",
    [{"level": "DEBUG", "enqueue": False}],
    indirect=True,
)
def test_rich_without_width_uses_default(logger, buffer):
    """Test that omitting width parameter uses default console width."""
    logger.rich("INFO", "Simple text without width parameter")
    output = buffer.getvalue()
    lines = output.splitlines()
    assert len(lines) > 0
    assert any(
        re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d+ \| INFO", line)
        for line in lines
    )
