# logurich

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

Logurich combines standard-library logging with live Rich renderables, structured
context, text and JSON output, and an optional multiprocessing queue.

## Installation

```bash
pip install logurich
pip install "logurich[click]"
```

## Quick start

```python
from rich.panel import Panel

from logurich import get_logger, init_logger

init_logger("INFO", console="plain", file="json", enqueue=False)
logger = get_logger(__name__)

logger.info("Processed %s items", 12, batch="b-42")

request_logger = logger.bind(
    request_id=logger.ctx("req-42", style="cyan")
)
request_logger.info("Request completed", duration_ms=17)

with logger.contextualize(user_id="alice"):
    logger.info("Authenticated")

logger.rich(
    "INFO",
    Panel("Service ready", border_style="green"),
    title="Startup",
    prefix=True,
    width=80,
)
```

Context values display their key (`[batch=b-42]`), whether they are raw or
wrapped in `ctx()`. Use `ctx()` to apply a style, rename the key with `label=`,
or hide it with `show_key=False`. Context precedence is:

```text
contextualize()/global context < bind() < per-call keywords
```

Every keyword that is not one of stdlib's four (`exc_info`, `stack_info`,
`stacklevel`, `extra`) is context; rendering options are parameters of
`rich()`. To log a stdlib name as context, bind it: `logger.bind(exc_info=...)`.

`bind()`, `new()`, `unbind()`, and `try_unbind()` always return a new
`LogurichLogger`; the original adapter is never mutated. `None` is a real
context value. Remove bound values with `unbind()` or `try_unbind()`, remove
selected ambient values with `global_context_unset()`, or clear all ambient
values with `global_clear_context()`.

## Standard-library compatibility

`get_logger(name)` returns an explicit `logging.LoggerAdapter` around
`logging.getLogger(name)`. It preserves positional `%s` formatting,
`exc_info`, `stack_info`, `stacklevel`, custom numeric levels, normal `extra`,
and the usual logger properties and handler methods.

Each call builds a new adapter, so `get_logger("app") is get_logger("app")` is
`False` even though both wrap the same stdlib logger. Adapters are cheap and
hold only their own bound context; level, handlers, and propagation live on the
shared stdlib logger. Compare `logger.name` rather than adapter identity.

Third-party loggers remain ordinary stdlib loggers:

```python
import logging

logging.getLogger("third.party").info(
    "Request completed",
    extra={"request_id": "req-42"},
)
```

When Logurich is configured, flat third-party `extra` fields are displayed as
context. Third-party loggers do not receive `.ctx()`, `.rich()`, `.bind()`, or
`.contextualize()` methods. A reusable library should not call `init_logger()`;
the application owns handler configuration and shutdown.

## Output modes

Console and file formats are independent:

```python
init_logger(
    "INFO",
    console="rich",       # auto | rich | plain | json
    file="json",          # text | json
    log_filename="app.log",
)
```

The defaults are `console="plain"` and `file="text"`.

`auto` answers "is a human reading this?", not "how pretty can output be": it
resolves to plain text on a TTY and to JSON otherwise, and it never selects the
Rich handler. Rich rendering changes how output is laid out, so it stays an
explicit opt-in via `console="rich"`.

When set, `LOGURICH_OUTPUT` always takes precedence over `console=` and
`--logger-console`; it affects only the console mode. Unset the variable to
honour the Python or CLI argument. An unrecognised value emits a `UserWarning`
and falls back to the configured mode, so a typo in a shared environment cannot
break startup. `LOGURICH_EXTRA_*` values continue to be included in JSON
`record.extra`.

JSON output never renders Rich objects as ASCII art. Text-file output renders
them without ANSI escape codes, while JSON serialises them as structured data
under `record.renderables`, leaving `text` and `record.message` free of borders
and box drawing characters. The JSON schema otherwise keeps the public `text`
and `record` structure from Logurich 0.9.

```json
{
  "type": "table",
  "title": "Metrics",
  "columns": ["Name", "Value"],
  "rows": [["requests", "42"]]
}
```

`Table`, `Panel`, `Tree`, `Syntax`, `Markdown`, `Rule`, `Layout`, `Group` and
`Columns` have dedicated shapes; `Padding`, `Align` and `Constrain` are
unwrapped. Any other Rich object degrades to `{"type": "text", "text": ...}` and
any non-renderable value to `{"type": "object", "repr": ...}`. Strings passed to
`logger.rich()` are not structured: they stay in `text`. Nesting is capped at
four levels and tables at 100 rows, with a `"truncated": true` marker.

The same converter is public, so tools that build reports from Rich objects can
reuse it instead of re-rendering:

```python
from logurich import SCHEMA_VERSION, serialize_renderables

payload = serialize_renderables((table,), max_rows=None, styles=True)
```

`max_depth` and `max_rows` relax the caps (`max_rows=None` keeps every row), and
`styles=True` switches to fidelity mode: text values become
`{"text": ..., "spans": [...]}` objects instead of plain strings, where each
span carries `start`, `end`, `style` and an optional `link`. Fidelity mode also
adds `justify`, `no_wrap` and per-column `style` to tables, `border_style` and
alignments to panels, and `align`/`style` to rules. Log output always uses the
default mode, so enabling styles never changes what handlers emit.

`SCHEMA_VERSION` identifies the payload contract. New keys may be added within a
version; existing keys are never renamed or removed.

## Premarkup

Premarkup tags transform text *before* Rich parses styling markup. Unknown tags
are left untouched, so Rich still handles them:

```python
from logurich import process_premarkup_to_text

process_premarkup_to_text("[defang]http://evil.test/a[/defang]")
# Text: http[:]//evil[.]test/a
```

Three actions ship built in: `defang` (neutralise URLs, domains and e-mails),
`color-obs` (highlight observables) and `truncate-url` (shorten long URLs).
Tags may combine actions, which then run in priority order:
`[truncate-url defang]...[/truncate-url defang]`.

Register your own with `register_premarkup(name, handler, priority=...)`; lower
priorities run first. `unregister_premarkup()` removes one and
`premarkup_actions()` lists them in execution order.

Premarkup is a standalone utility: it is never applied automatically to log
records, so it costs nothing on the logging path. `process_premarkup()` returns
a markup string that must be handed to `Text.from_markup` for its escapes to
resolve; `process_premarkup_to_text()` does that for you and passes non-string
inputs through unchanged. Inputs longer than `MAX_PREMARKUP_INPUT` are returned
as-is, and untrusted content should go through `rich.markup.escape` first, since
the output is markup.

## Rich objects

`logger.rich(level, *renderables, title="", prefix=True, end="\n", width=None,
highlight=False)` accepts strings and live Rich objects such as `Panel` and
`Table`. Objects stay live until the destination handler renders them. The same
method works after `bind()` and with direct or queued logging.

For multiprocessing, serialisable Rich values reach the listener unchanged. If
a renderable cannot be pickled, Logurich explicitly falls back to a plain,
ANSI-free producer-side rendering; other unpicklable record values produce a
clear logging error. Such a fallback is a plain string, so in JSON output it
lands in `text` instead of `record.renderables`.

## Multiprocessing

Only the parent process owns console and file handlers. Every worker must attach
the shared queue explicitly:

```python
import multiprocessing as mp

from logurich import (
    LogLevels,
    configure_child_logging,
    get_log_levels,
    get_log_queue,
    get_logger,
    init_logger,
)


def worker(log_queue: mp.Queue, log_levels: LogLevels, worker_id: int) -> None:
    configure_child_logging(log_queue, levels=log_levels)
    get_logger(f"worker.{worker_id}").info("Worker ready", worker=worker_id)


def main() -> None:
    init_logger("INFO", enqueue=True)
    queue = get_log_queue()
    process = mp.Process(target=worker, args=(queue, get_log_levels(), 1))
    process.start()
    process.join()
```

`levels` is optional: without it a worker enqueues every record and the parent
applies the configured levels. Passing it lets the worker drop filtered records
before they are built and sent.

Execution-local context follows `ContextVar` rules: asyncio tasks inherit it,
but new threads and processes do not inherit it implicitly. Configure worker
context inside each worker.

## Click integration

The optional decorator adds `--logger-level`, `--logger-verbose`,
`--logger-filename`, `--logger-level-by-module`, and `--logger-console`:

```python
import click

from logurich import get_logger
from logurich.opt_click import click_logger_params


@click.command()
@click_logger_params
def cli() -> None:
    get_logger(__name__).info("Ready")
```

Examples: `my-cli --logger-console rich` or
`my-cli --logger-console auto`. The default is `plain`.

## Lifecycle

Repeated `init_logger()` calls are no-ops unless `force=True` is supplied.
Logurich registers shutdown hooks for short-lived programs; call
`shutdown_logger()` when deterministic teardown is needed in tests or before
reconfiguration.

Users upgrading from 0.9 should read the [v1 migration guide](docs/migration-v1.md).

## Development

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
```
