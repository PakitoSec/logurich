import multiprocessing as mp
import os
import random
import string
import time

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from logurich import (
    ctx,
    global_configure,
    global_set_context,
    init_logger,
    logger,
    mp_configure,
)


# Simulate some data to process
def generate_data(num_items):
    """Generate some random data items to process."""
    return [
        {
            "id": i,
            "content": "".join(random.choices(string.ascii_letters, k=10)),
            "complexity": random.randint(1, 10),
        }
        for i in range(num_items)
    ]


def process_item(item):
    """
    Process a single data item in a worker process.

    Args:
        item: The data item to process

    Returns:
        dict: The processed item result
    """
    # Configure logurich for this process
    mp_configure(logger)

    # Set context variables for this item
    global_set_context(item=ctx(str(item["id"]), label="item", style="cyan"))

    try:
        # Log the start of processing
        logger.info(f"Processing item {item['id']}")

        # Simulate processing time based on complexity
        processing_time = item["complexity"] * 0.1
        time.sleep(processing_time)

        # For more complex items, show detailed information with rich logging
        if item["complexity"] > 7:
            table = Table(title=f"Item {item['id']} Details")
            table.add_column("Attribute")
            table.add_column("Value")
            for k, v in item.items():
                table.add_row(str(k), str(v))

            logger.rich(
                "INFO",
                Panel(
                    f"Complex item {item['id']} requires special handling",
                    border_style="yellow",
                ),
                table,
                title=f"Complex Item {item['id']}",
            )

            # Simulate additional processing for complex items
            time.sleep(0.2)

        # Simulate occasional errors
        if random.random() < 0.1:  # 10% chance of error
            raise ValueError(f"Error processing item {item['id']}")

        # Return the processed result
        result = {
            "id": item["id"],
            "original": item["content"],
            "processed": item["content"][::-1],  # Just reverse the string for demo
            "process_id": os.getpid(),
            "success": True,
        }

        logger.debug(f"Successfully processed item {item['id']}")
        return result

    except Exception as e:
        logger.exception(f"Failed to process item {item['id']}")
        return {
            "id": item["id"],
            "error": str(e),
            "process_id": os.getpid(),
            "success": False,
        }


def init_worker():
    """Initialize each worker process in the pool."""
    # Configure logurich for this process
    mp_configure(logger)

    # Add process-specific context
    pid = os.getpid()
    global_set_context(worker=ctx(f"Worker-{pid}", style="magenta", show_key=True))

    logger.info(f"Worker process {pid} initialized")


def main():
    # Initialize the logger with rich handler
    init_logger("INFO", log_verbose=2, rich_handler=False)

    with global_configure(group=ctx("DataProcessor", style="green", show_key=True)):
        logger.rich(
            "INFO",
            Panel("Starting parallel data processing example", border_style="blue"),
            title="Initialization",
        )

        # Generate sample data
        num_items = 20
        data = generate_data(num_items)

        # Show data summary
        table = Table(title="Processing Queue")
        table.add_column("ID")
        table.add_column("Content")
        table.add_column("Complexity")

        # Only show a sample of items if there are many
        display_items = data[:5] if len(data) > 5 else data
        for item in display_items:
            table.add_row(str(item["id"]), item["content"], str(item["complexity"]))
        if len(data) > 5:
            table.add_row("...", "...", "...")

        logger.rich("INFO", table, title=f"Items to Process: {num_items}")

        # Create a process pool with initialized workers
        num_processes = min(4, mp.cpu_count())
        logger.info(f"Creating process pool with {num_processes} workers")

        # Process the data in parallel
        start_time = time.time()
        results = []

        with mp.Pool(processes=num_processes, initializer=init_worker) as pool:
            # Use apply_async for more control over the processing
            pending_tasks = []
            for item in data:
                task = pool.apply_async(process_item, (item,))
                pending_tasks.append((item["id"], task))

            # Monitor and log progress
            completed = 0
            while pending_tasks:
                time.sleep(0.1)  # Small delay to reduce CPU usage
                newly_completed = []

                for item_id, task in pending_tasks:
                    if task.ready():
                        results.append(task.get())
                        newly_completed.append((item_id, task))
                        completed += 1

                if newly_completed:
                    # Remove completed tasks from pending list
                    for item in newly_completed:
                        pending_tasks.remove(item)

                    # Log progress
                    progress_pct = (completed / num_items) * 100
                    logger.info(
                        f"Progress: {completed}/{num_items} items ({progress_pct:.1f}%)"
                    )

        # Process complete, summarize results
        end_time = time.time()
        processing_time = end_time - start_time

        # Count successes and failures
        successes = sum(1 for r in results if r["success"])
        failures = len(results) - successes

        # Create results table
        results_table = Table(title="Processing Results")
        results_table.add_column("Metric")
        results_table.add_column("Value")

        results_table.add_row("Total Items", str(len(results)))
        results_table.add_row("Successful", Text(str(successes), style="green bold"))
        results_table.add_row(
            "Failed", Text(str(failures), style="red bold" if failures > 0 else "green")
        )
        results_table.add_row("Processing Time", f"{processing_time:.2f} seconds")
        results_table.add_row("Items/Second", f"{num_items / processing_time:.2f}")

        # Log a sample of the results
        sample_results = Table(title="Sample Results")
        sample_results.add_column("ID")
        sample_results.add_column("Original")
        sample_results.add_column("Processed")
        sample_results.add_column("Process ID")
        sample_results.add_column("Status")

        for result in results[:5]:
            status_style = "green" if result["success"] else "red"
            status_text = "Success" if result["success"] else "Failed"

            if result["success"]:
                sample_results.add_row(
                    str(result["id"]),
                    result["original"],
                    result["processed"],
                    str(result["process_id"]),
                    Text(status_text, style=status_style),
                )
            else:
                sample_results.add_row(
                    str(result["id"]),
                    "N/A",
                    "N/A",
                    str(result["process_id"]),
                    Text(f"{status_text}: {result['error']}", style=status_style),
                )

        # Log summary with rich logging
        logger.rich(
            "INFO",
            results_table,
            sample_results if results else None,
            title="Processing Summary",
        )

        # Final status message
        status = (
            "SUCCESS"
            if failures == 0
            else "WARNING"
            if failures < num_items * 0.2
            else "ERROR"
        )
        message = (
            "All items processed successfully"
            if failures == 0
            else f"Completed with {failures} failures"
            if failures > 0
            else ""
        )

        logger.rich(
            status,
            Panel(
                message,
                border_style="green"
                if failures == 0
                else "yellow"
                if failures < num_items * 0.2
                else "red",
            ),
            title="Process Complete",
        )


if __name__ == "__main__":
    # Set the start method for multiprocessing
    mp.set_start_method("spawn", force=True)
    main()
