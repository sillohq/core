"""
sillo.work.queue.workers — Process-level queue worker with signal handling.

Inspired by Laravel's ``queue:work`` command.  A ``QueueWorker`` pulls
jobs from a connection, deserialises them, runs them through middleware,
and handles retries / failures.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
import traceback
import importlib
from typing import Annotated, Any, Dict, List, Optional, Set

from typing_extensions import Doc

from .connection import QueueConnection, ConnectionManager
from .failed import FailedJobRepository, MemoryFailedRepository
from .job import Job
from .payloads import PayloadSerializer

logger = logging.getLogger("sillo.work.queue.workers")


class WorkerOptions:
    """Configuration for a :class:`QueueWorker`."""

    def __init__(
        self,
        *,
        concurrency: Annotated[int, Doc("Number of simultaneous workers.")] = 4,
        memory_limit: Annotated[
            int, Doc("Max memory in MB before restarting worker.")
        ] = 128,
        timeout: Annotated[float, Doc("Max seconds a job may run.")] = 60.0,
        sleep: Annotated[float, Doc("Seconds to sleep when queue is empty.")] = 3.0,
        max_jobs: Annotated[
            int, Doc("Process this many jobs before restarting. 0 = unlimited.")
        ] = 0,
        max_exec_time: Annotated[
            float, Doc("Max seconds the worker runs before restarting. 0 = unlimited.")
        ] = 0,
        queues: Annotated[
            List[str],
            Doc("Queue names to listen on. First queue has highest priority."),
        ] = ["default"],
        backoff: Annotated[float, Doc("Base backoff seconds for retries.")] = 0.0,
    ):
        """Init

        Returns:
            [description]

        Raises:
            [description]
        """
        self.concurrency = concurrency
        self.memory_limit = memory_limit
        self.timeout = timeout
        self.sleep = sleep
        self.max_jobs = max_jobs
        self.max_exec_time = max_exec_time
        self.queues = queues
        self.backoff = backoff


class QueueWorker:
    """Long-running process that pulls jobs from a queue connection.

    Usage::

        worker = QueueWorker(manager, serializer, failed_repo, options=WorkerOptions(concurrency=4))
        await worker.run()
    """

    def __init__(
        self,
        manager: Annotated[ConnectionManager, Doc("Connection broker.")],
        serializer: Annotated[PayloadSerializer, Doc("Payload codec.")],
        failed_repo: Annotated[FailedJobRepository, Doc("Failed job storage.")],
        *,
        options: Annotated[
            Optional[WorkerOptions], Doc("Worker configuration.")
        ] = None,
    ):
        """Init

        Args:
            manager: [description]
            serializer: [description]
            failed_repo: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.manager = manager
        self.serializer = serializer
        self.failed_repo = failed_repo
        self.options = options or WorkerOptions()
        self._running = False
        self._shutting_down = False
        self._paused = False
        self._active: Set[asyncio.Task] = set()
        self._jobs_processed = 0
        self._started_at = 0.0

    async def run(self) -> None:
        """Start the worker loop. Blocks until stopped."""
        self._running = True
        self._started_at = time.time()
        self._register_signals()

        workers = [
            asyncio.create_task(self._run_worker(i))
            for i in range(self.options.concurrency)
        ]
        logger.info(
            "QueueWorker started — concurrency=%d queues=%s",
            self.options.concurrency,
            self.options.queues,
        )

        await asyncio.gather(*workers, return_exceptions=True)
        logger.info("QueueWorker stopped — processed=%d", self._jobs_processed)

    def stop(self) -> None:
        """Signal the worker to shut down gracefully."""
        self._running = False

    def pause(self) -> None:
        """Pause job processing (workers sleep until resumed)."""
        self._paused = True
        logger.info("QueueWorker paused")

    def resume(self) -> None:
        """Resume job processing."""
        self._paused = False
        logger.info("QueueWorker resumed")

    def _register_signals(self) -> None:
        """Register Signals

        Returns:
            [description]

        Raises:
            [description]
        """
        try:
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self.stop)
        except NotImplementedError:
            pass

    async def _run_worker(self, worker_id: int) -> None:
        """Run Worker

        Args:
            worker_id: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        while self._running:
            if self._paused:
                await asyncio.sleep(1)
                continue

            job_data = None
            queue_name = self.options.queues[0]

            try:
                for qname in self.options.queues:
                    conn = self.manager.connection(qname)
                    popped = await conn.pop(qname, timeout=self.options.sleep)
                    if popped:
                        job_id, payload_str = popped
                        job_data = self.serializer.deserialize(payload_str)
                        job_data["_job_id"] = job_id
                        queue_name = qname
                        break

                if job_data is None:
                    continue

                await self._process_job(conn, queue_name, job_data, worker_id)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("[worker-%d] loop crash", worker_id)

    async def _process_job(
        self,
        conn: QueueConnection,
        queue_name: str,
        job_data: Dict[str, Any],
        worker_id: int,
    ) -> None:
        """Process Job

        Args:
            conn: [description]
            queue_name: [description]
            job_data: [description]
            worker_id: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        job_id = job_data.get("_job_id", "unknown")
        job_class_name = job_data.get("job", "unknown")

        try:
            job_cls = self._resolve_job_class(job_class_name)
            job_instance = self._build_job(job_cls, job_data)
            job_instance._job_id = job_id

            await job_instance.fire()
            await conn.ack(queue_name, job_id)
            self._jobs_processed += 1
            logger.debug("[worker-%d] ✓ %s", worker_id, job_class_name)

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("[worker-%d] ✗ %s: %s", worker_id, job_class_name, exc)

            try:
                await self.failed_repo.log(
                    queue=queue_name,
                    job_id=job_id,
                    job_class=job_class_name,
                    payload=json.dumps(job_data.get("data", {})),
                    exception=tb,
                )
            except Exception:
                logger.exception("Failed to log failed job")

    @staticmethod
    def _build_job(job_cls: type, job_data: Dict[str, Any]) -> Any:
        """Reconstruct the job from what was queued.

        Two payload shapes exist. ``dispatch`` records the call —
        ``{"args": [...], "kwargs": {...}}`` — and :meth:`Job.payload` records
        the instance's attributes under ``data``. Reading only ``data`` meant a
        dispatched job was rebuilt with no arguments at all: it ran, reported
        success, and used its defaults.

        Args:
            job_cls: The class to build.
            job_data: The decoded payload.

        Returns:
            The job instance to run.
        """
        if "args" in job_data or "kwargs" in job_data:
            return job_cls(*job_data.get("args", []), **job_data.get("kwargs", {}))
        return job_cls(**job_data.get("data", {}))

    def _resolve_job_class(self, name: str) -> type:
        """Find the class that handles a queued payload.

        Args:
            name: What the payload names, either ``module.Class`` as
                :meth:`Dispatchable.job_reference` writes it, or a bare class
                name from a payload queued by an older release.

        Returns:
            The job class.

        Raises:
            RuntimeError: If nothing of that name can be found, saying what
                would make it findable.
        """
        module_path, _, attribute = name.rpartition(".")
        if module_path:
            module = importlib.import_module(module_path)
            return getattr(module, attribute)

        # A bare name: search the classes that have been imported. This is how
        # payloads written before job references were qualified still run, and
        # it is why a project imports its jobs in one package — a class nobody
        # imported is a class this cannot find.
        found = self._search_subclasses(name)
        if found is not None:
            return found

        raise RuntimeError(
            f"Cannot resolve job class: {name}. Import it before the worker "
            f"starts — a project's jobs package is the usual place — or queue "
            f"it from a release that records where the class lives."
        )

    @staticmethod
    def _search_subclasses(name: str) -> "type | None":
        """Depth-first search of every imported job class for *name*."""
        from .job import Dispatchable

        seen: set = set()
        stack = list(Dispatchable.__subclasses__())
        while stack:
            candidate = stack.pop()
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate.__name__ == name:
                return candidate
            stack.extend(candidate.__subclasses__())
        return None


class WorkerPool:
    """Manage multiple :class:`QueueWorker` instances.

    Usage::

        pool = WorkerPool()
        pool.add(worker1).add(worker2)
        await pool.start()
        await pool.shutdown()
    """

    def __init__(self):
        """Init

        Returns:
            [description]

        Raises:
            [description]
        """
        self._workers: List[QueueWorker] = []
        self._tasks: List[asyncio.Task] = []

    def add(self, worker: QueueWorker) -> "WorkerPool":
        """Add

        Args:
            worker: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._workers.append(worker)
        return self

    async def start(self) -> None:
        """Start

        Returns:
            [description]

        Raises:
            [description]
        """
        self._tasks = [asyncio.create_task(w.run()) for w in self._workers]

    async def shutdown(self) -> None:
        """Shutdown

        Returns:
            [description]

        Raises:
            [description]
        """
        for w in self._workers:
            w.stop()
        await asyncio.gather(*self._tasks, return_exceptions=True)
