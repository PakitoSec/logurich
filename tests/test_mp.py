import logging
import multiprocessing as mp
import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from rich.panel import Panel
from rich.table import Table

import logurich.core as core
from logurich import (
    configure_child_logging,
    ctx,
    get_log_levels,
    get_log_queue,
    get_logger,
    global_context_configure,
    init_logger,
    rich_get_console,
    shutdown_logger,
)
from logurich.struct import logger_state


def worker_process(queue):
    configure_child_logging(queue)
    logging.getLogger("workers.basic").info("Test message from child process")


def worker_process_context(queue):
    configure_child_logging(queue)
    with global_context_configure(task_id=ctx("task-id", show_key=True)):
        logging.getLogger("workers.context").info("Message with context")


def worker_with_rich_logging(queue):
    configure_child_logging(queue)
    panel = Panel("Test rich panel")
    table = Table(title="Test table")
    table.add_column("Column 1")
    table.add_column("Column 2")
    table.add_row("Value 1", "Value 2")
    get_logger("workers.rich").rich("INFO", panel, table, title="Rich Test")


def test_configure_child_logging_routes_records_to_parent(buffer):
    init_logger("DEBUG", enqueue=True)
    log_queue = get_log_queue()

    process = mp.Process(target=worker_process, args=(log_queue,))
    process.start()
    process.join()
    assert process.exitcode == 0

    logging.getLogger("parent").info("Parent message")
    shutdown_logger()

    output = buffer.getvalue()
    assert "Test message from child process" in output
    assert "Parent message" in output


def test_child_process_context_is_rendered(buffer):
    init_logger("DEBUG", enqueue=True)
    log_queue = get_log_queue()

    process = mp.Process(target=worker_process_context, args=(log_queue,))
    process.start()
    process.join()
    assert process.exitcode == 0

    shutdown_logger()
    assert "task_id=task-id" in buffer.getvalue()


def test_rich_logging_in_child_process(buffer):
    init_logger("DEBUG", enqueue=True)
    log_queue = get_log_queue()

    process = mp.Process(target=worker_with_rich_logging, args=(log_queue,))
    process.start()
    process.join()
    assert process.exitcode == 0

    shutdown_logger()
    output = buffer.getvalue()
    assert "Column 1" in output
    assert "Column 2" in output
    assert "Value 1" in output
    assert "Value 2" in output
    assert "Rich Test" in output


def test_child_adopts_parent_levels_with_spawn(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = tmp_path / "spawn_child_levels.py"
    script_path.write_text(
        textwrap.dedent(
            """
            import logging
            import multiprocessing as mp

            from logurich import (
                configure_child_logging,
                get_log_levels,
                get_log_queue,
                get_logger,
                init_logger,
                shutdown_logger,
            )


            def worker_reports_level(queue, levels):
                configure_child_logging(queue, levels=levels)
                log = get_logger("workers.level")
                log.info(
                    "effective=%s debug_enabled=%s",
                    logging.getLogger().getEffectiveLevel(),
                    log.isEnabledFor(logging.DEBUG),
                )
                log.debug("this debug must not reach the parent")


            def main():
                init_logger("INFO", enqueue=True)
                log_queue = get_log_queue()
                try:
                    process = mp.Process(
                        target=worker_reports_level,
                        args=(log_queue, get_log_levels()),
                    )
                    process.start()
                    process.join()
                    assert process.exitcode == 0
                finally:
                    shutdown_logger()


            if __name__ == "__main__":
                mp.set_start_method("spawn", force=True)
                main()
            """
        )
    )
    env = os.environ.copy()
    pythonpath = str(repo_root / "src")
    if env.get("PYTHONPATH"):
        pythonpath = f"{pythonpath}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "effective=20 debug_enabled=False" in result.stdout
    assert "must not reach the parent" not in result.stdout


def test_child_levels_default_to_notset_without_explicit_levels():
    child_root = logging.getLogger("tests.child-levels-fallback")
    core._apply_child_levels(None, child_root)

    assert child_root.level == logging.NOTSET
    assert logger_state["min_level"] is None
    shutdown_logger()


def test_child_root_level_is_a_permissive_floor():
    child_root = logging.getLogger("tests.child-levels-floor")
    core._apply_child_levels((logging.WARNING, {"noisy": logging.DEBUG}), child_root)

    assert child_root.level == logging.DEBUG
    assert logger_state["min_level"] == logging.WARNING
    assert logger_state["level_by_module"] == {"noisy": logging.DEBUG}
    shutdown_logger()


def test_get_log_levels_returns_a_detached_copy():
    init_logger("WARNING", level_by_module={"noisy": "DEBUG"}, enqueue=True)
    levels = get_log_levels()
    shutdown_logger()

    assert levels == (logging.WARNING, {"noisy": logging.DEBUG})
    assert levels[1] is not logger_state["level_by_module"]


def test_get_log_levels_requires_initialization():
    with pytest.raises(RuntimeError, match="init_logger"):
        get_log_levels()


def test_unpickleable_rich_value_falls_back_to_text(buffer):
    init_logger("INFO", enqueue=True)
    get_logger("tests.queue-fallback").rich(
        "INFO", lambda: "not pickleable", title="Fallback"
    )
    shutdown_logger()

    output = buffer.getvalue()
    assert "Fallback" in output
    assert "lambda" in output


def test_plain_record_skips_pickle_validation(monkeypatch):
    record = logging.LogRecord(
        "tests.queue-plain-fast-path",
        logging.INFO,
        __file__,
        1,
        "Ready",
        (),
        None,
    )

    def fail_pickle(_value):
        raise AssertionError("plain records should not be preflight pickled")

    monkeypatch.setattr(core.pickle, "dumps", fail_pickle)

    prepared = core._LogurichQueueHandler(None).prepare(record)

    assert prepared.message == "Ready"
    assert prepared.context == {}
    assert prepared.renderables == ()


def test_pickleable_renderables_use_one_validation_pass(monkeypatch):
    panel = Panel("ready")
    record = logging.LogRecord(
        "tests.queue-fast-path",
        logging.INFO,
        __file__,
        1,
        "Ready",
        (),
        None,
    )
    record._logurich_record = True
    record._logurich_metadata = ("renderables",)
    record.renderables = (panel,)

    dumped: list[object] = []
    pickle_dumps = core.pickle.dumps

    def track_pickle(value):
        dumped.append(value)
        return pickle_dumps(value)

    monkeypatch.setattr(core.pickle, "dumps", track_pickle)

    prepared = core._LogurichQueueHandler(None).prepare(record)

    assert dumped == [prepared]
    assert prepared.renderables == (panel,)


@pytest.mark.parametrize("raise_exceptions", [False, True])
def test_unpickleable_context_uses_stdlib_error_policy(
    monkeypatch, capsys, buffer, raise_exceptions
):
    monkeypatch.setattr(logging, "raiseExceptions", raise_exceptions)
    init_logger("INFO", enqueue=True)
    get_logger("tests.queue-context").info("bad", callback=lambda: None)
    shutdown_logger()

    captured = capsys.readouterr()
    assert "bad" not in buffer.getvalue()
    if raise_exceptions:
        assert "--- Logging error ---" in captured.err
        assert "serialisable context values" in captured.err
    else:
        assert captured.err == ""


def test_interpreter_exit_stops_queue_listener_without_thread_error(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = tmp_path / "queue_listener_exit.py"
    script_path.write_text(
        textwrap.dedent(
            """
            import logging

            from logurich import init_logger


            def main():
                init_logger("INFO", enqueue=True)
                logging.getLogger("exit").info("Interpreter exit test")


            if __name__ == "__main__":
                main()
            """
        )
    )

    env = os.environ.copy()
    pythonpath = str(repo_root / "src")
    if env.get("PYTHONPATH"):
        pythonpath = f"{pythonpath}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Interpreter exit test" in result.stdout
    assert "Exception in thread" not in result.stderr
    assert "handle is closed" not in result.stderr


def test_spawn_pool_initializer_can_configure_child_logging(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = tmp_path / "spawn_pool_logging.py"
    script_path.write_text(
        textwrap.dedent(
            """
            import logging
            import multiprocessing as mp

            from logurich import (
                configure_child_logging,
                get_log_levels,
                get_log_queue,
                init_logger,
                shutdown_logger,
            )


            def init_worker(log_queue, log_levels):
                configure_child_logging(log_queue, levels=log_levels)


            def process_item(item):
                logging.getLogger("workers.pool").info("Pool item %s", item)
                return item * 2


            def main():
                init_logger("INFO", enqueue=True)
                log_queue = get_log_queue()
                try:
                    with mp.Pool(
                        processes=2,
                        initializer=init_worker,
                        initargs=(log_queue, get_log_levels()),
                    ) as pool:
                        results = pool.map(process_item, [1, 2, 3])
                    assert results == [2, 4, 6]
                finally:
                    shutdown_logger()


            if __name__ == "__main__":
                mp.set_start_method("spawn", force=True)
                main()
            """
        )
    )
    env = os.environ.copy()
    pythonpath = str(repo_root / "src")
    if env.get("PYTHONPATH"):
        pythonpath = f"{pythonpath}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.skipif(not hasattr(os, "fork"), reason="fork() is not available")
def test_console_lock_is_released_in_forked_child():
    """A lock held at fork time must not deadlock the child.

    ``os.fork()`` only clones the calling thread, so an inherited locked
    ``RLock`` would never be released and the first log call in the child would
    block forever.
    """
    console = rich_get_console()
    stale_lock = console._lock
    stale_lock.acquire()

    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            signal.alarm(10)  # never hang the suite if the fix regresses
            child_console = rich_get_console()
            assert child_console is console
            assert child_console._lock is not stale_lock
            logging.getLogger("workers.fork").warning("child is alive")
            os.write(write_fd, b"1")
        except BaseException:
            os.write(write_fd, b"0")
        finally:
            os._exit(0)

    os.close(write_fd)
    try:
        outcome = os.read(read_fd, 1)
        _, status = os.waitpid(pid, 0)
    finally:
        os.close(read_fd)
        stale_lock.release()

    assert status == 0
    assert outcome == b"1", "forked child inherited a locked console"
