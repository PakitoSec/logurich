import logging
import multiprocessing as mp
import os
import random
import string
import time

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from logurich import (
    configure_child_logging,
    ctx,
    get_log_queue,
    global_context_configure,
    global_context_set,
    init_logger,
)


def generate_data(num_items):
    return [
        {
            "id": i,
            "content": "".join(random.choices(string.ascii_letters, k=10)),
            "complexity": random.randint(1, 10),
        }
        for i in range(num_items)
    ]


def init_worker(log_queue):
    configure_child_logging(log_queue)


def process_item(item):
    logger = logging.getLogger("processor.worker")
    global_context_set(item=ctx(str(item["id"]), label="item", style="cyan"))

    try:
        logger.info("Processing item %s", item["id"])
        time.sleep(item["complexity"] * 0.1)

        if item["complexity"] > 7:
            table = Table(title=f"Item {item['id']} Details")
            table.add_column("Attribute")
            table.add_column("Value")
            for key, value in item.items():
                table.add_row(str(key), str(value))

            logger.info(
                "Complex item %s requires special handling",
                item["id"],
                extra={
                    "renderables": (
                        Panel(
                            f"Complex item {item['id']} requires special handling",
                            border_style="yellow",
                        ),
                        table,
                    )
                },
            )

        if random.random() < 0.1:
            raise ValueError(f"Error processing item {item['id']}")

        result = {
            "id": item["id"],
            "original": item["content"],
            "processed": item["content"][::-1],
            "process_id": os.getpid(),
            "success": True,
        }
        logger.debug("Successfully processed item %s", item["id"])
        return result
    except Exception:
        logger.exception("Failed to process item %s", item["id"])
        return {
            "id": item["id"],
            "error": f"Error processing item {item['id']}",
            "process_id": os.getpid(),
            "success": False,
        }


def worker_entry(item):
    return process_item(item)


def main():
    init_logger("INFO", log_verbose=2, enqueue=True)
    log_queue = get_log_queue()
    logger = logging.getLogger("processor.main")

    with global_context_configure(
        group=ctx("DataProcessor", style="green", show_key=True)
    ):
        logger.info(
            "Starting parallel data processing example",
            extra={
                "renderables": (
                    Panel(
                        "Starting parallel data processing example",
                        border_style="blue",
                    ),
                )
            },
        )

        data = generate_data(20)

        table = Table(title="Processing Queue")
        table.add_column("ID")
        table.add_column("Content")
        table.add_column("Complexity")
        for item in data[:5]:
            table.add_row(str(item["id"]), item["content"], str(item["complexity"]))
        table.add_row("...", "...", "...")
        logger.info("Items to process", extra={"renderables": (table,)})

        start_time = time.time()
        # Pool tasks cannot receive the queue directly under spawn, so configure
        # child logging once when each worker process starts.
        with mp.Pool(
            processes=min(4, mp.cpu_count()),
            initializer=init_worker,
            initargs=(log_queue,),
        ) as pool:
            results = pool.map(worker_entry, data)

        elapsed = time.time() - start_time
        successes = sum(1 for result in results if result["success"])
        failures = len(results) - successes

        results_table = Table(title="Processing Results")
        results_table.add_column("Metric")
        results_table.add_column("Value")
        results_table.add_row("Total Items", str(len(results)))
        results_table.add_row("Successful", Text(str(successes), style="green bold"))
        results_table.add_row(
            "Failed",
            Text(str(failures), style="red bold" if failures > 0 else "green"),
        )
        results_table.add_row("Processing Time", f"{elapsed:.2f} seconds")

        sample_results = Table(title="Sample Results")
        sample_results.add_column("ID")
        sample_results.add_column("Status")
        sample_results.add_column("Process ID")
        for result in results[:5]:
            status_style = "green" if result["success"] else "red"
            status_text = "Success" if result["success"] else "Failed"
            sample_results.add_row(
                str(result["id"]),
                Text(status_text, style=status_style),
                str(result["process_id"]),
            )

        logger.info(
            "Processing summary",
            extra={"renderables": (results_table, sample_results)},
        )


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
