"""
sillo.work.queue.job — Laravel-style dispatchable jobs.

A ``Job`` encapsulates a unit of work that is serialised and pushed onto
a queue.  Jobs support:

* Middleware pipelines (throttle, retry, log)
* Automatic retry with exponential backoff
* Timeout enforcement
* Unique job locking (prevent duplicates)
* Chaining and batching
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
import traceback
from typing import (
    Annotated,
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
)

from typing_extensions import Doc

logger = logging.getLogger("sillo.work.queue.job")


class Dispatchable:
    """Mixin that adds ``.dispatch()`` / ``.dispatch_after()`` to any Job class."""

    _connection: ClassVar[Optional[Any]] = None
    _queue_name: ClassVar[str] = "default"

    @classmethod
    def dispatch(cls, *args: Any, **kwargs: Any) -> str:
        """Push the job onto its configured queue immediately.

        Returns the job ID.
        """
        return cls.dispatch_after(0, *args, **kwargs)

    @classmethod
    def dispatch_after(
        cls, delay: Annotated[int, Doc("Seconds to delay.")], *args: Any, **kwargs: Any
    ) -> str:
        """Push the job onto its queue after *delay* seconds."""
        if cls._connection is None:
            raise RuntimeError(
                f"No queue connection configured for {cls.__name__}. Call Job.set_connection() first."
            )
        payload = json.dumps(
            {"job": cls.__name__, "args": args, "kwargs": kwargs}, default=str
        )
        return asyncio.get_event_loop().run_until_complete(
            cls._connection.push(cls._queue_name, payload, delay=delay)
        )

    @classmethod
    def on_queue(
        cls, queue: Annotated[str, Doc("Queue name.")]
    ) -> Type["Dispatchable"]:
        """Set the queue name for this job class."""
        cls._queue_name = queue
        return cls

    @classmethod
    def on_connection(
        cls, connection: Annotated[Any, Doc("QueueConnection instance.")]
    ) -> Type["Dispatchable"]:
        """Set the connection for this job class."""
        cls._connection = connection
        return cls

    @classmethod
    def dispatch_sync(cls, *args: Any, **kwargs: Any) -> Any:
        """Execute the job immediately in the current process (bypasses the queue)."""
        instance = cls(*args, **kwargs)
        return asyncio.get_event_loop().run_until_complete(instance.handle())


class Job(Dispatchable):
    """Base class for all queue jobs.

    Subclass and implement ``handle()``::

        class SendWelcomeEmail(Job):
            queue = "emails"
            tries = 3
            timeout = 30

            def __init__(self, user_id: str):
                self.user_id = user_id

            async def handle(self):
                user = await User.get(id=self.user_id)
                await send_email(user.email, "Welcome!")

    Dispatch from anywhere::

        SendWelcomeEmail.dispatch("user-42")
        SendWelcomeEmail.dispatch_after(300, "user-42")  # 5 min delay
    """

    queue: ClassVar[str] = "default"
    connection_name: ClassVar[str] = "default"
    tries: ClassVar[int] = 1
    timeout: ClassVar[Optional[float]] = 30.0
    backoff: ClassVar[int] = 0
    delete_when_completed: ClassVar[bool] = True
    middleware: ClassVar[List[Any]] = []

    def __init__(self, *args: Any, **kwargs: Any):
        """Init

        Returns:
            [description]

        Raises:
            [description]
        """
        self._job_id: Optional[str] = None
        self._attempts: int = 0
        self._started_at: float = 0.0

    async def handle(self) -> Any:
        """Override this method with the job's core logic."""
        raise NotImplementedError("Subclasses must implement handle()")

    async def failed(self, exception: Exception) -> None:
        """Called when the job has permanently failed. Override for custom handling."""
        pass

    def middleware_pipeline(self) -> List[Any]:
        """Return the middleware stack for this job."""
        return list(self.__class__.middleware)

    async def fire(self) -> Any:
        """Execute the job through its middleware pipeline. Called by the worker."""
        self._started_at = time.time()
        pipeline = self.middleware_pipeline()

        async def call_handle():
            """Call Handle

            Returns:
                [description]

            Raises:
                [description]
            """
            if self.timeout:
                return await asyncio.wait_for(self.handle(), timeout=self.timeout)
            return await self.handle()

        handler = call_handle
        for mw in reversed(pipeline):
            handler = mw(handler)

        return await handler()

    def max_tries(self) -> int:
        """Max Tries

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.__class__.tries

    def retry_after(self) -> int:
        """Retry After

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.__class__.backoff

    def display_name(self) -> str:
        """Display Name

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.__class__.__name__

    def payload(self) -> Dict[str, Any]:
        """Payload

        Returns:
            [description]

        Raises:
            [description]
        """
        return {
            "job": self.__class__.__name__,
            "maxTries": self.max_tries(),
            "timeout": self.timeout,
            "data": self.__dict__,
        }


def dispatch(job_class: Type[Job], *args: Any, **kwargs: Any) -> str:
    """Convenience function to dispatch any Job subclass."""
    return job_class.dispatch(*args, **kwargs)
