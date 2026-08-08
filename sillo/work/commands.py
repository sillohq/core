"""Queue and scheduler operations, as functions.

These are the operations a command line
expose, so that ``sillo-start``, a management script or a container entrypoint
can start a worker without each one reassembling the same five objects.

The assembly is the point. Running a worker means building a connection, a
serialiser, a failed-job store and an options object, wiring them into a
``QueueWorker`` and handling signals — five imports and thirty lines that every
project would otherwise copy, and get subtly wrong.

Usage::

    from sillo.work.commands import run_worker

    await run_worker(url="redis://localhost:6379", queues=["default", "email"])

``SyncConnection`` — the default — keeps jobs in the process that queued them.
It is convenient for a single process and wrong for anything else: nothing is
shared between an application and a worker, and nothing survives a restart.
Pass a Redis URL and the connection is chosen for you.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from collections.abc import Callable
from typing import Annotated, Any

from typing_extensions import Doc

logger = logging.getLogger("sillo.work")


def connection_for(
    url: Annotated[
        str | None,
        Doc(
            "Broker URL. A redis:// URL gives a shared queue; None keeps it in-process."
        ),
    ] = None,
    *,
    prefix: Annotated[str, Doc("Key prefix for Redis.")] = "sillo:queue:",
) -> Any:
    """Build the queue connection a URL describes.

    Returns:
        A :class:`RedisConnection` for a ``redis://`` URL, otherwise a
        :class:`SyncConnection`.

    Raises:
        ValueError: If *url* names a scheme sillo has no connection for.
    """
    from .queue import RedisConnection, SyncConnection

    if not url:
        return SyncConnection()

    scheme = url.split("://", 1)[0].lower()
    if scheme in {"redis", "rediss"}:
        return RedisConnection(url=url, prefix=prefix)
    raise ValueError(
        f"No queue connection for '{scheme}://'. Use a redis:// URL, "
        "or omit the URL for an in-process queue."
    )


def build_worker(
    *,
    url: Annotated[
        str | None, Doc("Broker URL. None keeps the queue in-process.")
    ] = None,
    queues: Annotated[
        list[str] | None, Doc("Queues to consume, highest priority first.")
    ] = None,
    concurrency: Annotated[int, Doc("Jobs to run at once.")] = 4,
    timeout: Annotated[float, Doc("Seconds a single job may run.")] = 60.0,
    max_jobs: Annotated[int, Doc("Restart after this many jobs. 0 is unlimited.")] = 0,
    connection: Annotated[
        Any, Doc("A ready connection, instead of building one from url.")
    ] = None,
    failed_repository: Annotated[Any, Doc("Where failed jobs are kept.")] = None,
    prefix: Annotated[str, Doc("Key prefix for Redis.")] = "sillo:queue:",
) -> Any:
    """Assemble a worker without running it.

    Useful when you want to inspect or wrap the worker — adding middleware,
    say — before starting it. :func:`run_worker` calls this and then runs it.

    Returns:
        A configured :class:`QueueWorker`.
    """
    from .queue import (
        ConnectionManager,
        MemoryFailedRepository,
        PayloadSerializer,
        QueueWorker,
        WorkerOptions,
    )

    manager = ConnectionManager()
    # `add`, not `register` — the latter does not exist, and calling it fails
    # after the database has already connected, which reads as a database fault.
    manager.add("default", connection or connection_for(url, prefix=prefix))

    return QueueWorker(
        manager,
        PayloadSerializer(),
        failed_repository or MemoryFailedRepository(),
        options=WorkerOptions(
            concurrency=concurrency,
            timeout=timeout,
            max_jobs=max_jobs,
            queues=queues or ["default"],
        ),
    )


async def run_worker(
    *,
    url: Annotated[
        str | None, Doc("Broker URL. None keeps the queue in-process.")
    ] = None,
    queues: Annotated[
        list[str] | None, Doc("Queues to consume, highest priority first.")
    ] = None,
    concurrency: Annotated[int, Doc("Jobs to run at once.")] = 4,
    timeout: Annotated[float, Doc("Seconds a single job may run.")] = 60.0,
    max_jobs: Annotated[int, Doc("Restart after this many jobs. 0 is unlimited.")] = 0,
    connection: Annotated[
        Any, Doc("A ready connection, instead of building one from url.")
    ] = None,
    failed_repository: Annotated[Any, Doc("Where failed jobs are kept.")] = None,
    prefix: Annotated[str, Doc("Key prefix for Redis.")] = "sillo:queue:",
    handle_signals: Annotated[bool, Doc("Stop cleanly on SIGINT and SIGTERM.")] = True,
) -> None:
    """Run a queue worker until it is stopped.

    Blocks. Import the modules that define your jobs before calling, or a
    queued payload cannot be resolved back to the class that handles it.

    With ``handle_signals``, SIGINT and SIGTERM ask the worker to finish the job
    in flight and exit — which is what a container runtime sends, and the
    difference between a clean shutdown and a job killed halfway through.
    """
    worker = build_worker(
        url=url,
        queues=queues,
        concurrency=concurrency,
        timeout=timeout,
        max_jobs=max_jobs,
        connection=connection,
        failed_repository=failed_repository,
        prefix=prefix,
    )

    if handle_signals:
        _install_stop_handler(worker.stop)

    logger.info(
        "Queue worker starting — queues=%s concurrency=%s broker=%s",
        queues or ["default"],
        concurrency,
        url or "in-process",
    )
    await worker.run()


async def run_scheduler(
    register: Annotated[
        Callable[[Any], Any] | None,
        Doc("Called with the manager to register tasks before it starts."),
    ] = None,
    *,
    manager: Annotated[
        Any, Doc("An existing SchedulerManager, instead of a new one.")
    ] = None,
    handle_signals: Annotated[bool, Doc("Stop cleanly on SIGINT and SIGTERM.")] = True,
) -> None:
    """Run the scheduler until it is stopped.

    Blocks. *register* receives the manager and should attach the project's
    tasks to it — usually the ``register_tasks`` function a project already has.
    """
    from .scheduler import SchedulerManager

    scheduler = manager or SchedulerManager()
    if register is not None:
        result = register(scheduler)
        if asyncio.iscoroutine(result):
            await result

    stopping = asyncio.Event()
    if handle_signals:
        _install_stop_handler(stopping.set)

    await scheduler.start()
    logger.info("Scheduler started — %s task(s)", len(scheduler.list()))
    try:
        await stopping.wait()
    finally:
        await scheduler.stop()


def _install_stop_handler(stop: Callable[[], Any]) -> None:
    """Ask *stop* to run on SIGINT and SIGTERM, where the loop allows it.

    ``add_signal_handler`` is unavailable on Windows and inside a loop that is
    not the main thread's. Failing to install one should not stop a worker from
    running, so it is attempted and let go.
    """
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError, AttributeError):
            loop.add_signal_handler(signum, stop)
