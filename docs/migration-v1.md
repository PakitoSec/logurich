# Migrating from Logurich 0.9 to v1

Logurich v1 replaces the 0.9 logging API atomically. There are no deprecated
aliases or hidden compatibility paths.

## Logger creation

Use Logurich's explicit adapter when you need Logurich methods:

```diff
-logger = logging.getLogger("app")
+logger = get_logger("app")
 logger.rich("INFO", panel)
```

`get_logger()` no longer returns the same object as `logging.getLogger()`, and
it is not an instance of `logging.Logger`. It also returns a new adapter on
every call, so `get_logger("app") is get_logger("app")` is `False`; compare
`logger.name` instead. Multiple adapters may wrap the same stdlib logger
without sharing bound context, while level, handlers, and propagation stay on
the shared stdlib logger. `BoundLogger` was removed; all binding operations
return `LogurichLogger`.

Importing Logurich no longer calls `logging.setLoggerClass()` and no longer
re-classes existing loggers, so `logging.getLogger("app").rich(...)` now raises
`AttributeError` instead of silently working as it did in 0.9. Records emitted
by third-party stdlib loggers are still captured and formatted by Logurich's
handlers.

## Context and renderables

Pass Logurich context directly as keywords, and rendering options to `rich()`:

```diff
 logger.info(
     "Login",
-    extra={"context": {"user": ctx("alice")}},
+    user=ctx("alice"),
 )

-logger.info("Summary", extra={"renderables": (panel, table)})
+logger.rich("INFO", panel, table, title="Summary")
```

The two old Logurich payloads in `extra` raise a migration error on a
`LogurichLogger`, as does a bare `renderables=` keyword. Normal stdlib `extra`
remains supported. On third-party stdlib loggers, all `extra` fields—including
fields literally named `context` or `renderables`—are treated as flat context
and receive no legacy interpretation.

All context values now display their keys, including values built with `ctx()`,
which hid the key in 0.9. Pass `ctx(value, show_key=False)` to hide a key, or
`label=` to rename it; styling a value no longer changes whether its key is
shown. Rename `global_context_configure(...)` to `global_context(...)` for a
temporary ambient context; `global_context_set()` keeps its name.
`None` is now a real value: `bind(key=None)` and
`global_context_set(key=None)` retain the key. Call `unbind("key")` to remove a
bound value, `global_context_unset("key")` to remove an ambient value, or
`global_clear_context()` to clear all ambient values in the current execution.

Logurich reserves no call keywords of its own and never will: every keyword that
is not one of stdlib's four (`exc_info`, `stack_info`, `stacklevel`, `extra`) is
context, so `logger.info("job", start=t0, end=t1)` logs both values. Rendering
options—`prefix`, `width`, `end`, `highlight`—are parameters of `rich()`. A
keyword that closely resembles a stdlib one still logs as context but emits a
`UserWarning` naming the likely intended keyword. If you need a stdlib name as a
context key, bind it: `logger.bind(exc_info="...")`.

## Output configuration

Console and file modes are now independent, and `rich_handler` was removed:

```diff
-init_logger("INFO", rich_handler=True)
+init_logger("INFO", console="rich")

-init_logger("INFO", rich_handler=False)
+init_logger("INFO", console="plain")
```

The old `LOGURICH_RICH` and `LOGURICH_SERIALIZE` variables are ignored, and
`init_logger()` emits a `UserWarning` when either is present so a stale variable
in a shared environment cannot break startup. Replace them with
`LOGURICH_OUTPUT=auto|rich|plain|json`, and set the file mode independently in
Python:

```python
init_logger("INFO", console="json", file="json")
```

When set, `LOGURICH_OUTPUT` always takes precedence over both the Python
`console=` argument and the Click `--logger-console` option. Unset the variable
to honour either explicit argument. An unrecognised value emits a `UserWarning`
and falls back to the configured mode rather than raising. It never changes the
file mode.

`auto` resolves to plain text on a TTY and to JSON otherwise. It never selects
the Rich handler, which stays an explicit `console="rich"` opt-in.

The Click flag changed from `--logger-rich` to the explicit choice
`--logger-console auto|rich|plain|json`. The old flag is an unknown option.
The matching parameter renamed too: `logurich.opt_click.LOGGER_PARAM_NAMES` now
ends with `logger_console`, and `click_logger_init()` takes
`logger_console: str` instead of `logger_rich: bool`.

## Module layout

Context helpers now live in `logurich.context` instead of `logurich.core`, so
submodule imports such as `from logurich.core import global_context_set` fail:

```diff
-from logurich.core import ContextValue, ctx, global_context_set
+from logurich import ContextValue, ctx, global_context_set
```

The package root re-exports every public name, so importing from `logurich`
keeps working across releases. `logurich.utils` (and `parse_bool_env`) was
removed, and two new modules were added: `logurich.premarkup` and
`logurich.serialize`. Premarkup is opt-in and never applied to log records
automatically, so 0.9 messages containing bracket tags render unchanged.

## Rich renderables in JSON output

JSON output no longer embeds the ASCII rendering of Rich objects. Both
`console="json"` and `file="json"` now emit structured data under
`record.renderables`, and `text` and `record.message` keep only the log line:

```diff
 {
-  "text": "2025-01-01 00:00:00.000 | INFO     | report\n# ┏━━━━━━━━━━┳━━━━━━━┓\n# ┃ Name     ┃ Value ┃\n# ┡━━━━━━━━━━╇━━━━━━━┩\n# │ requests │ 42    │\n# └──────────┴───────┘",
+  "text": "2025-01-01 00:00:00.000 | INFO     | report\n",
   "record": {
-    "message": "report\n# ┏━━━━━━━━━━┳━━━━━━━┓\n# ┃ Name     ┃ Value ┃..."
+    "message": "report",
+    "renderables": [
+      {
+        "type": "table",
+        "title": "Metrics",
+        "columns": ["Name", "Value"],
+        "rows": [["requests", "42"]]
+      }
+    ]
   }
 }
```

The key is omitted when a record carries no Rich object. Strings passed to
`logger.rich()` are unaffected and stay in `text`. `console="rich"`,
`console="plain"` and `file="text"` are unchanged. Update log pipelines that
grepped rendered tables out of `record.message`; read `record.renderables`
instead. Its shapes are documented in the README.

## Imports to find and replace

Search applications for:

- `logging.getLogger()` followed by `.ctx()`, `.rich()`, `.bind()`, or
  `.contextualize()`;
- `extra={"context": ...}` and `extra={"renderables": ...}`;
- `rich_handler`;
- `LOGURICH_RICH` and `LOGURICH_SERIALIZE`;
- imports of `BoundLogger`;
- imports of `logurich.utils` or `parse_bool_env`;
- imports of `ctx`, `ContextValue`, or `global_context_*` from `logurich.core`;
- `--logger-rich`, `LOGGER_PARAM_NAMES`, and `click_logger_init(logger_rich=...)`;
- `ctx(...)` calls that relied on the key being hidden by default;
- identity or `isinstance(..., logging.Logger)` checks on `get_logger()`;
- `bind(...=None)` calls that previously relied on `None` being ignored;
- `global_context_set(...=None)` calls that previously removed ambient values;
- JSON consumers parsing rendered tables or panels out of `record.message`.
