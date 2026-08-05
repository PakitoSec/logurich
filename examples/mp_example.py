import multiprocessing as mp
import random
import time

from rich.panel import Panel
from rich.table import Table

from logurich import (
    configure_child_logging,
    ctx,
    get_log_levels,
    get_log_queue,
    get_logger,
    global_context,
    init_logger,
)


def worker_function(log_queue, log_levels, worker_id):
    configure_child_logging(log_queue, levels=log_levels)
    logger = get_logger(f"workers.{worker_id}")

    with global_context(worker=ctx(f"Worker-{worker_id}")):
        logger.info("Worker %s starting", worker_id)
        logger.debug("Worker %s debug message", worker_id)

        table = Table(title=f"Worker {worker_id} Stats")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Process ID", str(mp.current_process().pid))
        table.add_row("Random Value", str(random.randint(1, 100)))

        logger.rich(
            "INFO",
            Panel(
                f"Worker {worker_id} is processing data",
                border_style="green",
            ),
            table,
            title=f"Worker {worker_id} status",
        )

        for i in range(3):
            logger.info("Worker %s step %s/3", worker_id, i + 1)
            time.sleep(random.uniform(0.1, 0.5))

        logger.rich(
            "INFO",
            Panel(
                f"Worker {worker_id} completed successfully",
                border_style="bold green",
            ),
            title=f"Worker {worker_id} completed successfully",
        )


def main() -> None:
    init_logger("INFO", log_verbose=2, enqueue=True)
    log_queue = get_log_queue()
    log_levels = get_log_levels()

    get_logger("main").info("Multiprocessing example starting")

    with global_context(process=ctx("Main-Process", style="magenta")):
        processes = [
            mp.Process(target=worker_function, args=(log_queue, log_levels, i + 1))
            for i in range(3)
        ]

        get_logger("main").rich(
            "INFO",
            Panel("Starting worker processes", border_style="blue"),
            title="Starting worker processes",
        )

        for process in processes:
            process.start()

        table = Table(title="Process Summary")
        table.add_column("Worker ID")
        table.add_column("PID")
        table.add_column("Status")

        for index, process in enumerate(processes, start=1):
            table.add_row(f"Worker {index}", str(process.pid), "Running")

        get_logger("main").rich("INFO", table, title="Workers started")

        for index, process in enumerate(processes, start=1):
            process.join()
            get_logger("main").info(
                "Worker %s (PID: %s) has completed",
                index,
                process.pid,
            )


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
