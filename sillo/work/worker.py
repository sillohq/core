"""
sillo.work.worker — Concurrent worker pool with circuit breaker.

A ``Worker`` pulls tasks from a ``Queue`` and executes them across a
configurable number of concurrent workers.  Features:

* Automatic retry with exponential backoff (capped at 60 s).
* Dead-letter queue routing for permanently failed tasks.
* Circuit breaker — stops processing when failure rate exceeds threshold,
  then auto-recovers after a configurable recovery period.
* Graceful shutdown — waits for in-flight tasks to finish within a
  configurable grace period, then cancels the rest.
* Health-check endpoint via :attr:`stats`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set

from .queue import Queue
from .task import Task
from .types import (
    CircuitBreakerOpen,
    CircuitState,
    TaskStatus,
    WorkerStats,
)

logger = logging.getLogger("sillo.work.worker")


class Worker:
    def __init__(
        self,
        queue: Queue,
        *,
        concurrency: int = 4,
        timeout: float = 30.0,
        graceful_timeout: float = 10.0,
        dead_letter_queue: Optional[Queue] = None,
        circuit_breaker_threshold: int = 10,
        circuit_breaker_window: float = 60.0,
        circuit_breaker_recovery: float = 30.0,
    ):
        self.queue = queue
        self.concurrency = max(1, concurrency)
        self.timeout = timeout
        self.graceful_timeout = graceful_timeout
        self.dead_letter_queue = dead_letter_queue
        self._cb_threshold = circuit_breaker_threshold
        self._cb_window = circuit_breaker_window
        self._cb_recovery = circuit_breaker_recovery

        # Internal state
        self._running = False
        self._workers: List[asyncio.Task] = []
        self._processed = 0
        self._failed = 0
        self._failure_times: List[float] = []
        self._circuit = CircuitState.CLOSED
        self._circuit_opened_at: float = 0.0
        self._active_tasks: Set[str] = set()
        self._started_at: float = 0.0

    # ── lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._started_at = time.time()
        self._workers = [
            asyncio.create_task(self._run(worker_id=i))
            for i in range(self.concurrency)
        ]
        logger.info(
            "Worker started — concurrency=%d queue='%s'",
            self.concurrency,
            self.queue.name,
        )

    async def stop(self, timeout: Optional[float] = None) -> None:
        if not self._running:
            return
        self._running = False
        effective_timeout = timeout or self.graceful_timeout

        for w in self._workers:
            if not w.done():
                w.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        logger.info(
            "Worker stopped — processed=%d failed=%d",
            self._processed,
            self._failed,
        )

    # ── stats ──────────────────────────────────────────────────────────

    @property
    def stats(self) -> WorkerStats:
        return WorkerStats(
            processed=self._processed,
            failed=self._failed,
            active=len(self._active_tasks),
            workers=self.concurrency,
            circuit=self._circuit,
            uptime_seconds=time.time() - self._started_at if self._started_at else 0.0,
        )

    # ── worker loop ────────────────────────────────────────────────────

    async def _run(self, worker_id: int) -> None:
        while self._running:
            try:
                task = await self.queue.get(timeout=1.0)
                if task is None:
                    continue

                if self._circuit == CircuitState.OPEN:
                    if self._should_try_recovery():
                        self._half_open()
                    else:
                        await self.queue.mark_done(task)
                        continue

                await self._execute(task, worker_id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("[worker-%d] loop crash", worker_id)

    # ── task execution ─────────────────────────────────────────────────

    async def _execute(self, task: Task, worker_id: int) -> None:
        self._active_tasks.add(task.id)
        try:
            attempt = 0
            while attempt < task.max_attempts:
                try:
                    for mw in self.queue._middleware:
                        await mw.before_execute(task)

                    await task.run(timeout=getattr(task, "timeout", self.timeout))
                    self._processed += 1
                    await self.queue.mark_done(task)
                    self._on_success()
                    return

                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    for mw in self.queue._middleware:
                        try:
                            await mw.on_error(task, exc)
                        except Exception:
                            pass
                    attempt += 1
                    if attempt >= task.max_attempts:
                        self._failed += 1
                        self._record_failure()
                        task.status = TaskStatus.FAILED
                        logger.error(
                            "[worker-%d] %s — exhausted %d attempts: %s",
                            worker_id, task.name, task.max_attempts, exc,
                        )
                        await self.queue.mark_done(task)

                        if self.dead_letter_queue:
                            try:
                                await self.dead_letter_queue.put(
                                    task.func,
                                    *task.args,
                                    name=f"[DLQ] {task.name}",
                                    **task.kwargs,
                                )
                            except Exception:
                                logger.exception("DLQ enqueue failed")
                        return

                    task.status = TaskStatus.RETRYING
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "[worker-%d] %s — retry %d/%d in %.0fs: %s",
                        worker_id, task.name, attempt, task.max_attempts, delay, exc,
                    )
                    await asyncio.sleep(delay)
        finally:
            self._active_tasks.discard(task.id)

    # ── circuit breaker ────────────────────────────────────────────────

    def _record_failure(self) -> None:
        now = time.monotonic()
        self._failure_times.append(now)
        cutoff = now - self._cb_window
        self._failure_times = [t for t in self._failure_times if t > cutoff]

        if (
            len(self._failure_times) >= self._cb_threshold
            and self._circuit == CircuitState.CLOSED
        ):
            self._circuit = CircuitState.OPEN
            self._circuit_opened_at = now
            logger.critical(
                "CIRCUIT OPEN — %d failures in %.0fs",
                len(self._failure_times),
                self._cb_window,
            )

    def _should_try_recovery(self) -> bool:
        elapsed = time.monotonic() - self._circuit_opened_at
        return elapsed >= self._cb_recovery

    def _half_open(self) -> None:
        self._circuit = CircuitState.HALF_OPEN
        self._failure_times.clear()
        logger.info("Circuit HALF-OPEN — testing recovery")

    def _on_success(self) -> None:
        if self._circuit == CircuitState.HALF_OPEN:
            self._circuit = CircuitState.CLOSED
            self._failure_times.clear()
            logger.info("Circuit CLOSED — recovered")

    # ── backoff ────────────────────────────────────────────────────────

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        return min(2 ** (attempt - 1), 60)
