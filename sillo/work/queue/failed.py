"""
sillo.work.queue.failed — Failed job persistence and inspection.

When a job exhausts all retry attempts, it is logged to a failed-job
repository.  Implementations can store failures in memory (development)
or in a database (production).
"""

from __future__ import annotations

import dataclasses
import time
from abc import ABC, abstractmethod
from typing import Annotated, Any, Dict, List, Optional

from typing_extensions import Doc


@dataclasses.dataclass
class FailedJob:
    """Record of a permanently failed job."""

    id: str
    queue: str
    job_class: str
    payload: str
    exception: str
    failed_at: float = dataclasses.field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """To Dict

        Returns:
            [description]

        Raises:
            [description]
        """
        return dataclasses.asdict(self)


class FailedJobRepository(ABC):
    """Abstract interface for persisting failed jobs."""

    @abstractmethod
    async def log(
        self,
        queue: Annotated[str, Doc("Queue name.")],
        job_id: Annotated[str, Doc("Job ID that failed.")],
        job_class: Annotated[str, Doc("Job class name.")],
        payload: Annotated[str, Doc("Serialised job payload.")],
        exception: Annotated[str, Doc("Traceback string.")],
    ) -> None:
        """Persist a failed job record."""
        ...

    @abstractmethod
    async def all(
        self,
        limit: Annotated[int, Doc("Max records to return.")] = 50,
        offset: Annotated[int, Doc("Skip this many.")] = 0,
    ) -> List[FailedJob]:
        """List all failed jobs, newest first."""
        ...

    @abstractmethod
    async def find(
        self, job_id: Annotated[str, Doc("Job ID to look up.")]
    ) -> Optional[FailedJob]:
        """Find a specific failed job by ID."""
        ...

    @abstractmethod
    async def forget(self, job_id: Annotated[str, Doc("Job ID to remove.")]) -> bool:
        """Remove a failed job record. Returns True if found."""
        ...

    @abstractmethod
    async def flush(self) -> None:
        """Remove all failed job records."""
        ...


class MemoryFailedRepository(FailedJobRepository):
    """In-memory failed job repository — for development."""

    def __init__(self):
        """Init

        Returns:
            [description]

        Raises:
            [description]
        """
        self._failed: List[FailedJob] = []

    async def log(
        self, queue: str, job_id: str, job_class: str, payload: str, exception: str
    ) -> None:
        """Log

        Args:
            queue: [description]
            job_id: [description]
            job_class: [description]
            payload: [description]
            exception: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._failed.append(
            FailedJob(
                id=job_id,
                queue=queue,
                job_class=job_class,
                payload=payload,
                exception=exception,
            )
        )

    async def all(self, limit: int = 50, offset: int = 0) -> List[FailedJob]:
        """All

        Args:
            limit: [description]
            offset: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return list(reversed(self._failed))[offset : offset + limit]

    async def find(self, job_id: str) -> Optional[FailedJob]:
        """Find

        Args:
            job_id: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        for fj in self._failed:
            if fj.id == job_id:
                return fj
        return None

    async def forget(self, job_id: str) -> bool:
        """Forget

        Args:
            job_id: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        before = len(self._failed)
        self._failed = [fj for fj in self._failed if fj.id != job_id]
        return len(self._failed) < before

    async def flush(self) -> None:
        """Flush

        Returns:
            [description]

        Raises:
            [description]
        """
        self._failed.clear()
