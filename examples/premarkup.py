from logurich import (
    console,
    get_logger,
    init_logger,
    premarkup_actions,
    process_premarkup_to_text,
    register_premarkup,
    unregister_premarkup,
)


def redact(text: str) -> str:
    return "".join("*" if char.isdigit() else char for char in text)


if __name__ == "__main__":
    init_logger("INFO", enqueue=False)
    logger = get_logger(__name__)

    console.rule("Built-in premarkup actions")
    samples = [
        "[defang]Reach out to http://evil.test/a or mail@evil.test[/defang]",
        "[truncate-url]Fetched https://example.test/very/long/path/report?id=7#x[/truncate-url]",
        "[color-obs]Observed evil.test during triage[/color-obs]",
        "[truncate-url defang]https://evil.test/a/b/c/d/e/f[/truncate-url defang]",
        "[bold]Unknown tags such as [nope]this[/nope] reach Rich untouched[/bold]",
    ]
    for sample in samples:
        console.print(process_premarkup_to_text(sample))

    console.rule("Custom action")
    register_premarkup("redact", redact, priority=5)
    console.print(process_premarkup_to_text("[redact]Ticket 12345 closed[/redact]"))
    names = ", ".join(action.name for action in premarkup_actions())
    console.print(f"Actions in execution order: {names}")
    unregister_premarkup("redact")

    logger.info("Premarkup demo complete", samples=len(samples))
