import logging
import multiprocessing as mp
import random
import time

from rich.panel import Panel
from rich.table import Table

from logurich import (
    configure_child_logging,
    ctx,
    get_log_queue,
    global_context_configure,
    init_logger,
)


def worker_function(log_queue, worker_id):
    configure_child_logging(log_queue)
    logger = logging.getLogger(f"workers.{worker_id}")

    with global_context_configure(worker=ctx(f"Worker-{worker_id}", show_key=True)):
        logger.info("Worker %s starting", worker_id)
        logger.debug("Worker %s debug message", worker_id)

        table = Table(title=f"Worker {worker_id} Stats")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Process ID", str(mp.current_process().pid))
        table.add_row("Random Value", str(random.randint(1, 100)))

        logger.info(
            "Worker %s status",
            worker_id,
            extra={
                "renderables": (
                    Panel(
                        f"Worker {worker_id} is processing data",
                        border_style="green",
                    ),
                    table,
                )
            },
        )

        for i in range(3):
            logger.info("Worker %s step %s/3", worker_id, i + 1)
            time.sleep(random.uniform(0.1, 0.5))

        logger.info(
            "Worker %s completed successfully",
            worker_id,
            extra={
                "renderables": (
                    Panel(
                        f"Worker {worker_id} completed successfully",
                        border_style="bold green",
                    ),
                )
            },
        )


def main() -> None:
    init_logger("INFO", log_verbose=2, enqueue=True)
    log_queue = get_log_queue()

    logging.getLogger("main").info("Multiprocessing example starting")

    with global_context_configure(
        process=ctx("Main-Process", style="magenta", show_key=True)
    ):
        processes = [
            mp.Process(target=worker_function, args=(log_queue, i + 1))
            for i in range(3)
        ]

        logging.getLogger("main").info(
            "Starting worker processes",
            extra={
                "renderables": (
                    Panel("Starting worker processes", border_style="blue"),
                )
            },
        )

        for process in processes:
            process.start()

        table = Table(title="Process Summary")
        table.add_column("Worker ID")
        table.add_column("PID")
        table.add_column("Status")

        for index, process in enumerate(processes, start=1):
            table.add_row(f"Worker {index}", str(process.pid), "Running")

        logging.getLogger("main").info(
            "Workers started",
            extra={"renderables": (table,)},
        )

        for index, process in enumerate(processes, start=1):
            process.join()
            logging.getLogger("main").info(
                "Worker %s (PID: %s) has completed",
                index,
                process.pid,
            )


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
