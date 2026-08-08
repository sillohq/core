"""
sillo.work.queue.batches — Job batching, chaining, and fan-out.

Batch multiple jobs together and track their collective completion.
Chain jobs so they run sequentially.  Fan-out a single job into many
parallel child jobs.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from typing_extensions import Doc

logger = logging.getLogger("sillo.work.queue.batches")


class Batch:
    """A named collection of jobs tracked for completion.

    Usage::

        batch = Batch("export-users", on_complete=notify_admin)
        batch.add(SendEmail.dispatch("user1@ex.com"))
        batch.add(SendEmail.dispatch("user2@ex.com"))
        await batch.dispatch()
    """

    def __init__(
        self,
        name: Annotated[str, Doc("Human-readable batch name.")],
        *,
        on_complete: Annotated[
            Callable[[Batch], Awaitable[None]] | None,
            Doc("Callback when all jobs finish."),
        ] = None,
        allow_failures: Annotated[
            bool, Doc("If True, individual failures don't fail the batch.")
        ] = False,
        timeout: Annotated[
            float | None, Doc("Max seconds before timing out the batch.")
        ] = None,
    ):
        """Init"""
        self.id = str(uuid.uuid4())
        self.name = name
        self._jobs: list[str] = []
        self._completed: set[str] = set()
        self._failed: dict[str, str] = {}
        self._on_complete = on_complete
        self._allow_failures = allow_failures
        self._timeout = timeout
        self._started_at: float = 0.0
        self._done = asyncio.Event()
        self._finished = False

    def add(
        self, job_id: Annotated[str, Doc("Job ID returned by dispatch().")]
    ) -> Batch:
        """Add a job to the batch. Returns self for chaining."""
        self._jobs.append(job_id)
        return self

    def mark_complete(
        self, job_id: Annotated[str, Doc("Job ID that completed successfully.")]
    ) -> None:
        """Mark a single job as done."""
        self._completed.add(job_id)
        self._check_done()

    def mark_failed(
        self,
        job_id: Annotated[str, Doc("Job ID that failed.")],
        error: Annotated[str, Doc("Error message.")],
    ) -> None:
        """Mark a single job as failed."""
        self._failed[job_id] = error
        if not self._allow_failures:
            self._finish()
        else:
            self._check_done()

    def _check_done(self) -> None:
        """Check Done"""
        total = len(self._jobs)
        done = len(self._completed) + len(self._failed)
        if total > 0 and done >= total:
            self._finish()

    def _finish(self) -> None:
        """Finish"""
        if self._finished:
            return
        self._finished = True
        self._done.set()
        if self._on_complete:
            asyncio.create_task(self._on_complete(self))  # ty: ignore[invalid-argument-type]

    async def wait(self, timeout: float | None = None) -> None:
        """Block until the batch completes or times out."""
        await asyncio.wait_for(self._done.wait(), timeout=timeout)

    @property
    def completed_count(self) -> int:
        """Completed Count"""
        return len(self._completed)

    @property
    def failed_count(self) -> int:
        """Failed Count"""
        return len(self._failed)

    @property
    def total(self) -> int:
        """Total"""
        return len(self._jobs)

    @property
    def is_done(self) -> bool:
        """Is Done"""
        return self._finished


class JobChain:
    """Run a sequence of jobs one after another.

    Usage::

        chain = JobChain()
        chain.then(JobA.dispatch("x")).then(JobB.dispatch("y"))
        await chain.run()
    """

    def __init__(self):
        """Init"""
        self._jobs: list[Callable[[], Awaitable[Any]]] = []

    def then(
        self,
        job: Annotated[
            Callable[[], Awaitable[Any]],
            Doc("Async callable (usually a job dispatch)."),
        ],
    ) -> JobChain:
        """Append a job to the chain."""
        self._jobs.append(job)
        return self

    async def run(self) -> list[Any]:
        """Execute all jobs sequentially. Returns list of results."""
        results = []
        for job in self._jobs:
            results.append(await job())
        return results
