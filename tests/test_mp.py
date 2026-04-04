import logging
import multiprocessing as mp
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from rich.panel import Panel
from rich.table import Table

from logurich import (
    configure_child_logging,
    ctx,
    get_log_queue,
    global_context_configure,
    init_logger,
    shutdown_logger,
)


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
    logging.getLogger("workers.rich").info(
        "Rich Test",
        extra={"renderables": (panel, table)},
    )


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
                get_log_queue,
                init_logger,
                shutdown_logger,
            )


            def init_worker(log_queue):
                configure_child_logging(log_queue)


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
                        initargs=(log_queue,),
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
