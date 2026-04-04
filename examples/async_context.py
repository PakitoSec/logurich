import asyncio
import logging
import multiprocessing as mp
import time

from logurich import (
    configure_child_logging,
    ctx,
    get_log_queue,
    global_context_configure,
    init_logger,
    shutdown_logger,
)

request_log = logging.getLogger("example.request")
db_log = logging.getLogger("example.db")
task_log = logging.getLogger("example.task")
thread_log = logging.getLogger("example.thread")
process_log = logging.getLogger("example.process")


async def fetch_user_profile() -> None:
    db_log.info("Loading user profile")
    await asyncio.sleep(0.05)
    db_log.info("User profile loaded")


async def background_async_step() -> None:
    task_log.info("Async task started")
    await asyncio.sleep(0.02)
    task_log.info("Async task finished")


def background_thread_step() -> None:
    thread_log.info("Thread task started")
    time.sleep(0.02)
    thread_log.info("Thread task finished")


def background_process_step(log_queue: mp.Queue, request_id: str) -> None:
    configure_child_logging(log_queue)
    with global_context_configure(
        request_id=ctx(request_id, show_key=True, style="bold cyan")
    ):
        process_log.info("Process task started")
        time.sleep(0.03)
        process_log.info("Process task finished")


async def run_process_step(log_queue: mp.Queue, request_id: str) -> None:
    process = mp.Process(
        target=background_process_step,
        args=(log_queue, request_id),
        name=f"worker-{request_id}",
    )
    process.start()
    try:
        await asyncio.to_thread(process.join)
    finally:
        if process.is_alive():
            process.terminate()
            await asyncio.to_thread(process.join)
    if process.exitcode not in (0, None):
        raise RuntimeError(
            f"Background process failed for {request_id} with exit code {process.exitcode}"
        )


async def handle_request(request_id: str, log_queue: mp.Queue) -> None:
    with global_context_configure(
        request_id=ctx(request_id, show_key=True, style="bold cyan")
    ):
        request_log.info("Request started")
        await fetch_user_profile()
        await asyncio.gather(
            background_async_step(),
            asyncio.to_thread(background_thread_step),
            run_process_step(log_queue, request_id),
        )
        request_log.info("Request finished")


async def main(log_queue: mp.Queue) -> None:
    await asyncio.gather(
        handle_request("req-100", log_queue),
        handle_request("req-200", log_queue),
    )


if __name__ == "__main__":
    init_logger("INFO", enqueue=True)
    log_queue = get_log_queue()
    try:
        asyncio.run(main(log_queue))
    finally:
        shutdown_logger()
