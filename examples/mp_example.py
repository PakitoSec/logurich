import multiprocessing as mp
import random
import time

from rich.panel import Panel
from rich.table import Table

from logurich import ctx, global_configure, init_logger, logger, mp_configure


def worker_function(worker_id):
    """
    Worker function that runs in a separate process.
    Shows how to configure logurich in a child process.
    """
    # Configure the logger in this process
    mp_configure(logger)

    # Set a context variable for this worker
    with global_configure(worker=ctx(f"Worker-{worker_id}", show_key=True)):
        # Log some basic messages
        logger.info(f"Worker {worker_id} starting")
        logger.debug(f"Worker {worker_id} debug message")

        # Use rich logging features
        table = Table(title=f"Worker {worker_id} Stats")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Process ID", str(mp.current_process().pid))
        table.add_row("Random Value", str(random.randint(1, 100)))

        logger.rich(
            "INFO",
            Panel(f"Worker {worker_id} is processing data", border_style="green"),
            table,
            title=f"Worker {worker_id} Status",
        )

        # Simulate some work
        for i in range(3):
            logger.info(f"Worker {worker_id} - Step {i + 1}/3")
            time.sleep(random.uniform(0.1, 0.5))

        # Log completion with a rich panel
        logger.rich(
            "SUCCESS",
            Panel(
                f"Worker {worker_id} completed successfully", border_style="bold green"
            ),
            title="Task Complete",
        )


def main():
    # Initialize the logger with verbose level 2 for more detailed process info
    # Log level INFO, with rich handler enabled
    init_logger("INFO", log_verbose=2)

    # Log the start of the program
    logger.info("Multiprocessing example starting")

    # Create context for the main process
    with global_configure(process=ctx("Main-Process", style="magenta", show_key=True)):
        # Create and start multiple worker processes
        num_workers = 3
        processes = []

        logger.rich(
            "INFO",
            Panel("Starting worker processes", border_style="blue"),
            title="Initialization",
        )

        # Create and start worker processes
        for i in range(num_workers):
            p = mp.Process(target=worker_function, args=(i + 1,))
            processes.append(p)
            p.start()
            logger.debug(f"Started worker {i + 1} with PID: {p.pid}")

        # Create a summary table
        table = Table(title="Process Summary")
        table.add_column("Worker ID")
        table.add_column("PID")
        table.add_column("Status")

        for i, p in enumerate(processes):
            table.add_row(f"Worker {i + 1}", str(p.pid), "Running")

        logger.rich("INFO", table, title="Workers Started")

        # Wait for all processes to complete
        for i, p in enumerate(processes):
            p.join()
            logger.info(f"Worker {i + 1} (PID: {p.pid}) has completed")

        # Log completion
        logger.rich(
            "SUCCESS",
            Panel(
                "All worker processes completed successfully", border_style="bold green"
            ),
            title="Multiprocessing Example Complete",
        )


if __name__ == "__main__":
    # Set the start method for multiprocessing (recommended for some platforms)
    mp.set_start_method("spawn", force=True)
    main()
