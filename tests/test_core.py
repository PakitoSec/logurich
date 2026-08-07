import asyncio
import inspect
import json
import logging
import subprocess
import sys
import threading
import warnings
from pathlib import Path

import pytest

import logurich
import logurich.core as core
from logurich import (
    CONSOLE_MODE_CHOICES,
    FILE_MODE_CHOICES,
    LogurichLogger,
    ctx,
    get_logger,
    global_clear_context,
    global_context,
    global_context_set,
    global_context_unset,
    init_logger,
    shutdown_logger,
)
from logurich.struct import logger_state


@pytest.mark.parametrize("enqueue", [False, True])
def test_level_and_positional_formatting(enqueue, buffer):
    init_logger("INFO", enqueue=enqueue)
    logger = get_logger("tests.level")

    logger.info("Hello, %s!", "world")
    logger.debug("filtered")
    shutdown_logger()

    output = buffer.getvalue()
    assert "Hello, world!" in output
    assert "filtered" not in output


@pytest.mark.parametrize(
    ("level_by_module", "expected_level"),
    [
        (None, logging.WARNING),
        ({"noisy": "ERROR"}, logging.WARNING),
        ({"noisy": "DEBUG"}, logging.DEBUG),
    ],
)
def test_root_level_uses_permissive_floor(level_by_module, expected_level):
    root = logging.getLogger()
    logger = logging.getLogger("tests.parent-level-floor")
    logger.setLevel(logging.NOTSET)

    try:
        init_logger(
            "WARNING",
            level_by_module=level_by_module,
            enqueue=False,
        )

        assert root.level == expected_level
        assert logger.isEnabledFor(logging.DEBUG) is (expected_level <= logging.DEBUG)
    finally:
        shutdown_logger()


def test_import_does_not_monkeypatch_logging(tmp_path):
    script = tmp_path / "check_import.py"
    script.write_text(
        "import logging\n"
        "logger_class = logging.getLoggerClass()\n"
        "root_class = type(logging.getLogger())\n"
        "import logurich\n"
        "assert logging.getLoggerClass() is logger_class\n"
        "assert type(logging.getLogger()) is root_class\n"
        "assert not hasattr(logging.getLogger('dependency'), 'rich')\n"
    )

    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=20
    )
    assert result.returncode == 0, result.stderr


def test_get_logger_returns_distinct_adapters_for_stdlib_logger():
    first = get_logger("tests.identity")
    second = get_logger("tests.identity")
    stdlib = logging.getLogger("tests.identity")

    assert isinstance(first, LogurichLogger)
    assert not isinstance(first, logging.Logger)
    assert first is not second
    assert first.logger is second.logger is stdlib
    assert not hasattr(stdlib, "bind")
    assert "BoundLogger" not in logurich.__all__
    assert not hasattr(logurich, "BoundLogger")


def test_logger_obtained_before_init_is_silent_at_info(capsys):
    shutdown_logger()
    get_logger("tests.before-init").info("must stay silent")
    captured = capsys.readouterr()
    assert "must stay silent" not in captured.out
    assert "must stay silent" not in captured.err


def test_stdlib_properties_and_methods_are_delegated():
    logger = get_logger("tests.delegate")
    handler = logging.NullHandler()
    original_level = logger.level
    original_propagate = logger.propagate
    original_disabled = logger.disabled
    try:
        logger.setLevel(logging.ERROR)
        logger.addHandler(handler)
        logger.propagate = False
        logger.disabled = True

        assert logger.name == "tests.delegate"
        assert logger.level == logging.ERROR
        assert handler in logger.handlers
        assert logger.propagate is False
        assert logger.disabled is True
        assert not logger.isEnabledFor(logging.INFO)
    finally:
        logger.removeHandler(handler)
        logger.level = original_level
        logger.propagate = original_propagate
        logger.disabled = original_disabled


def test_raw_context_displays_its_key(logger, buffer):
    logger.info("Login", user="alice")
    shutdown_logger()
    assert "[user=alice] Login" in buffer.getvalue()


def test_ctx_can_hide_or_rename_key(logger, buffer):
    logger.info("hidden", user=ctx("alice", show_key=False))
    logger.info("renamed", user=ctx("bob", label="account"))
    shutdown_logger()

    output = buffer.getvalue()
    assert "[alice] hidden" in output
    assert "[account=bob] renamed" in output


def test_ctx_displays_its_key_like_raw_values(logger, buffer):
    logger.info("Login", user=ctx("alice"))
    shutdown_logger()
    assert "[user=alice] Login" in buffer.getvalue()


@pytest.mark.parametrize("enqueue", [False, True])
def test_context_priority_global_bound_call(enqueue, buffer):
    init_logger("INFO", enqueue=enqueue)
    logger = get_logger("tests.priority").bind(value="bound")

    with logger.contextualize(value="global", scope="request"):
        logger.info("winner", value="call")
    shutdown_logger()

    output = buffer.getvalue()
    assert "value=call" in output
    assert "value=bound" not in output
    assert "value=global" not in output
    assert "scope=request" in output


def test_nested_context_restores_outer_value(logger, buffer):
    with global_context(request="outer"):
        logger.info("first")
        with global_context(request="inner"):
            logger.info("second")
        logger.info("third")
    logger.info("fourth")
    shutdown_logger()

    lines = [line for line in buffer.getvalue().splitlines() if line]
    assert "request=outer" in lines[0]
    assert "request=inner" in lines[1]
    assert "request=outer" in lines[2]
    assert "request=" not in lines[3]


def test_global_context_set_and_none_are_values(logger, buffer):
    global_context_set(result=None)
    logger.info("done")
    shutdown_logger()
    assert "result=None" in buffer.getvalue()


def test_context_removal_api_is_public():
    assert logurich.global_context_unset is global_context_unset
    assert logurich.global_clear_context is global_clear_context
    assert {"global_context_unset", "global_clear_context"} <= set(logurich.__all__)


def test_global_context_unset_removes_only_requested_keys(logger, buffer):
    global_context_set(request="req-1", tenant="acme", result=None)
    global_context_unset("request", "missing")
    logger.info("done")
    shutdown_logger()

    output = buffer.getvalue()
    assert "request=req-1" not in output
    assert "tenant=acme" in output
    assert "result=None" in output


def test_global_clear_context_removes_all_ambient_context(logger, buffer):
    global_context_set(request="req-1", tenant="acme")
    global_clear_context()
    logger.info("done")
    shutdown_logger()

    output = buffer.getvalue()
    assert "request=req-1" not in output
    assert "tenant=acme" not in output


def test_binding_is_immutable_and_always_returns_same_type():
    logger = get_logger("tests.bind")
    first = logger.bind(app="api", result=None)
    second = first.bind(request="req-1")

    assert type(first) is LogurichLogger
    assert type(second) is LogurichLogger
    assert logger._bound_context == {}
    assert set(first._bound_context) == {"app", "result"}
    assert set(second._bound_context) == {"app", "result", "request"}


def test_new_unbind_and_try_unbind():
    logger = get_logger("tests.binding-ops").bind(app="api", request="req-1")

    assert set(logger.unbind("request")._bound_context) == {"app"}
    assert set(logger.try_unbind("missing", "request")._bound_context) == {"app"}
    assert set(logger.new(user="alice")._bound_context) == {"user"}
    with pytest.raises(KeyError, match="missing"):
        logger.unbind("missing")


def test_two_bound_loggers_do_not_share_context(logger, buffer):
    logger.bind(worker="one").info("first")
    logger.bind(worker="two").info("second")
    shutdown_logger()

    lines = [line for line in buffer.getvalue().splitlines() if line]
    assert "worker=one" in lines[0] and "worker=two" not in lines[0]
    assert "worker=two" in lines[1] and "worker=one" not in lines[1]


def test_context_key_can_match_log_record_attribute(logger, buffer):
    logger.info("safe", name="context-name", levelno=999, message="context-message")
    shutdown_logger()
    output = buffer.getvalue()
    assert "name=context-name" in output
    assert "levelno=999" in output
    assert "message=context-message" in output


@pytest.mark.parametrize("key", ["context", "renderables"])
def test_legacy_logurich_extra_is_rejected(key):
    logger = get_logger("tests.legacy-extra")
    with pytest.raises(TypeError, match="no longer supported"):
        logger.info("legacy", extra={key: {"value": 1}})


def test_renderables_keyword_points_at_rich():
    logger = get_logger("tests.renderables-kwarg")
    with pytest.raises(TypeError, match="logger.rich"):
        logger.info("summary", renderables=("panel",))


@pytest.mark.parametrize(
    "key", ["end", "render_prefix", "render_width", "rich_highlight"]
)
def test_rendering_option_names_are_plain_context(logger, buffer, key):
    logger.info("job", **{key: "value"})
    shutdown_logger()
    output = buffer.getvalue()
    assert f"{key}=value" in output
    assert output.endswith("\n")


@pytest.mark.parametrize(
    ("key", "suggestion"),
    [("exc_inf", "exc_info"), ("stack_level", "stacklevel"), ("extra_", "extra")],
)
def test_misspelled_logging_keyword_warns(logger, buffer, key, suggestion):
    with pytest.warns(UserWarning, match=f"did you mean {suggestion!r}"):
        logger.info("typo", **{key: 1})
    shutdown_logger()
    assert f"{key}=1" in buffer.getvalue()


@pytest.mark.parametrize("key", ["user", "request_id", "duration", "endpoint"])
def test_plain_context_keys_do_not_warn(logger, key):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        logger.info("clean", **{key: "value"})
    shutdown_logger()


def test_regular_extra_mapping_is_copied_and_rendered(logger, buffer):
    extra = {"request_id": "req-42"}
    logger.info("request", extra=extra)
    shutdown_logger()
    assert extra == {"request_id": "req-42"}
    assert "request_id=req-42" in buffer.getvalue()


def test_third_party_stdlib_extra_is_flat_context(buffer):
    init_logger("INFO", enqueue=False)
    logging.getLogger("third.party").info(
        "dependency",
        extra={"request_id": "req-42", "context": {"legacy": True}},
    )
    shutdown_logger()

    output = buffer.getvalue()
    assert "request_id=req-42" in output
    assert "context={'legacy': True}" in output


def test_custom_numeric_level(logger, buffer):
    logging.addLevelName(35, "NOTICE")
    logger.log(35, "custom")
    shutdown_logger()
    assert "NOTICE" in buffer.getvalue()
    assert "custom" in buffer.getvalue()


def test_standard_stacklevel_points_to_caller(buffer):
    init_logger("INFO", console="json", enqueue=False)
    logger = get_logger("tests.standard-stacklevel")
    expected_line = inspect.currentframe().f_lineno + 1
    logger.info("source")
    shutdown_logger()

    payload = json.loads(buffer.getvalue().splitlines()[0])
    assert payload["record"]["line"] == expected_line
    assert payload["record"]["function"] == "test_standard_stacklevel_points_to_caller"


@pytest.mark.parametrize("enqueue", [False, True])
def test_exception_and_stack_info(enqueue, buffer):
    init_logger("INFO", enqueue=enqueue)
    logger = get_logger("tests.exception")
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("failed")
    logger.info("stack", stack_info=True)
    shutdown_logger()

    output = buffer.getvalue()
    assert "ValueError: boom" in output
    assert "Stack (most recent call last)" in output


@pytest.mark.parametrize(
    ("console", "file_mode", "terminal", "expected"),
    [
        ("PLAIN", "JSON", True, ("plain", "json")),
        ("auto", "text", True, ("plain", "text")),
        ("auto", "text", False, ("json", "text")),
        ("rich", "json", False, ("rich", "json")),
    ],
)
def test_resolve_output_modes(console, file_mode, terminal, expected):
    modes = core._resolve_output_modes(
        console=console, file=file_mode, is_terminal=terminal, env={}
    )
    assert (modes.console, modes.file) == expected


def test_output_mode_environment_override():
    modes = core._resolve_output_modes(
        console="plain",
        file="json",
        is_terminal=False,
        env={"LOGURICH_OUTPUT": "RICH"},
    )
    assert (modes.console, modes.file) == ("rich", "json")


def test_output_mode_environment_override_falls_back_when_invalid():
    with pytest.warns(UserWarning, match="LOGURICH_OUTPUT"):
        modes = core._resolve_output_modes(
            console="plain",
            file="text",
            is_terminal=True,
            env={"LOGURICH_OUTPUT": "nope"},
        )
    assert (modes.console, modes.file) == ("plain", "text")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"console": "invalid", "file": "text"},
        {"console": "plain", "file": "invalid"},
    ],
)
def test_resolve_output_modes_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        core._resolve_output_modes(is_terminal=True, env={}, **kwargs)


def test_public_output_choices():
    assert CONSOLE_MODE_CHOICES == ("auto", "rich", "plain", "json")
    assert FILE_MODE_CHOICES == ("text", "json")
    assert not hasattr(logurich, "OutputModes")
    assert not hasattr(logurich, "resolve_output_modes")


@pytest.mark.parametrize("legacy", ["LOGURICH_RICH", "LOGURICH_SERIALIZE"])
def test_init_warns_and_ignores_legacy_environment(monkeypatch, buffer, legacy):
    monkeypatch.setenv(legacy, "1")
    with pytest.warns(UserWarning, match="LOGURICH_OUTPUT"):
        init_logger("INFO", enqueue=False)
    logger = get_logger("tests.legacy-env")
    logger.info("hello")
    shutdown_logger()
    output = buffer.getvalue()
    assert "hello" in output
    assert not output.lstrip().startswith("{")


def test_removed_rich_handler_parameter_is_rejected():
    with pytest.raises(TypeError, match="rich_handler"):
        init_logger("INFO", rich_handler=True)  # type: ignore[call-arg]


def test_json_console_contract(buffer):
    init_logger("INFO", console="json", enqueue=False)
    get_logger("tests.json").info("Login %s", "ok", user=ctx("alice", style="red"))
    shutdown_logger()

    payload = json.loads(buffer.getvalue().splitlines()[0])
    assert payload["record"]["message"] == "Login ok"
    assert payload["record"]["extra"]["user"] == "alice"
    assert payload["record"]["level"] == {"name": "INFO", "no": logging.INFO}
    assert "renderables" not in payload["record"]
    assert "\x1b[" not in json.dumps(payload)


@pytest.mark.parametrize(
    ("console_mode", "file_mode"),
    [("rich", "json"), ("plain", "json"), ("json", "text")],
)
def test_console_and_file_modes_are_independent(
    console_mode, file_mode, tmp_path, buffer
):
    init_logger(
        "INFO",
        console=console_mode,
        file=file_mode,
        log_filename="app.log",
        log_folder=str(tmp_path),
        rotation=None,
        enqueue=False,
    )
    get_logger("tests.outputs").info("output", user="alice")
    shutdown_logger()

    file_text = (tmp_path / "app.log").read_text()
    if file_mode == "json":
        assert json.loads(file_text)["record"]["extra"]["user"] == "alice"
    else:
        assert "output" in file_text
        assert not file_text.lstrip().startswith("{")
    assert "\x1b[" not in file_text


def test_init_is_idempotent_and_force_reconfigures(buffer):
    init_logger("ERROR", enqueue=False)
    assert init_logger("DEBUG", enqueue=False) is None
    get_logger("tests.force").info("still filtered")

    init_logger("DEBUG", enqueue=False, force=True)
    get_logger("tests.force").debug("now visible")
    shutdown_logger()

    output = buffer.getvalue()
    assert "still filtered" not in output
    assert "now visible" in output


def test_context_is_isolated_from_new_thread(logger, buffer):
    with global_context(request="main"):
        thread = threading.Thread(target=lambda: logger.info("thread"))
        thread.start()
        thread.join()
        logger.info("main")
    shutdown_logger()

    lines = [line for line in buffer.getvalue().splitlines() if line]
    assert "request=main" not in next(line for line in lines if "thread" in line)
    assert "request=main" in next(line for line in lines if " main" in line)


def test_context_is_propagated_to_asyncio_tasks(logger, buffer):
    async def child() -> None:
        logger.info("async child")

    async def run() -> None:
        with global_context(request="async"):
            await asyncio.create_task(child())

    asyncio.run(run())
    shutdown_logger()
    assert "request=async" in buffer.getvalue()


def test_concurrent_bound_loggers_do_not_leak(logger, buffer):
    barrier = threading.Barrier(3)

    def emit(worker: str) -> None:
        bound = logger.bind(worker=worker)
        barrier.wait()
        bound.info("from-%s", worker)

    threads = [threading.Thread(target=emit, args=(worker,)) for worker in ("a", "b")]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    shutdown_logger()

    lines = [line for line in buffer.getvalue().splitlines() if line]
    line_a = next(line for line in lines if "from-a" in line)
    line_b = next(line for line in lines if "from-b" in line)
    assert "worker=a" in line_a and "worker=b" not in line_a
    assert "worker=b" in line_b and "worker=a" not in line_b


def test_init_logger_registers_shutdown_hooks_once(monkeypatch):
    registered: list[object] = []
    thread_registered: list[object] = []

    monkeypatch.setitem(logger_state, "atexit_registered", False)
    monkeypatch.setitem(logger_state, "threading_atexit_registered", False)
    monkeypatch.setattr("logurich.core.atexit.register", registered.append)
    monkeypatch.setattr(
        "logurich.core.threading._register_atexit", thread_registered.append
    )

    init_logger("INFO", enqueue=False)
    shutdown_logger()
    init_logger("INFO", enqueue=False)
    shutdown_logger()

    assert registered == [shutdown_logger]
    assert thread_registered == [shutdown_logger]


@pytest.mark.parametrize("enqueue", [False, True])
def test_caller_attribution_points_at_user_frame(enqueue, buffer):
    init_logger("DEBUG", console="json", enqueue=enqueue)
    logger = get_logger("tests.caller")
    expected: dict[str, int] = {}

    expected["info-call"] = inspect.currentframe().f_lineno + 1
    logger.info("info-call")

    expected["warning-call"] = inspect.currentframe().f_lineno + 1
    logger.warning("warning-call")

    try:
        raise ValueError("boom")
    except ValueError:
        expected["exception-call"] = inspect.currentframe().f_lineno + 1
        logger.exception("exception-call")

    expected["rich-call"] = inspect.currentframe().f_lineno + 1
    logger.rich("INFO", "body", title="rich-call")

    bound = logger.bind(a=1).bind(b=2)
    expected["bound-call"] = inspect.currentframe().f_lineno + 1
    bound.info("bound-call")

    shutdown_logger()

    records = {}
    for line in buffer.getvalue().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)["record"]
        records[record["message"].splitlines()[0]] = record

    assert set(records) == set(expected)
    for message, line_no in expected.items():
        record = records[message]
        assert record["function"] == "test_caller_attribution_points_at_user_frame"
        assert record["line"] == line_no
        assert record["file"]["path"] == str(Path(__file__))


def test_version_matches_project_metadata():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    assert f'version = "{logurich.__version__}"' in pyproject.read_text()
