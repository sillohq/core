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


def _run_blocking(coro: Awaitable[Any], called: str, instead: str) -> Any:
    """Run *coro* to completion on a fresh event loop.

    A running event loop cannot be re-entered, so calling this from async code
    is a programming error rather than something to work around. When that
    happens the coroutine is closed and the caller is told which awaitable to
    use instead.

    Args:
        coro: The coroutine to run.
        called: The name of the blocking method, for the error message.
        instead: The async form the caller should use, for the error message.

    Returns:
        Whatever the coroutine returns.

    Raises:
        RuntimeError: If an event loop is already running in this thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)  # ty: ignore[invalid-argument-type]

    coro.close()  # ty: ignore[unresolved-attribute]
    raise RuntimeError(
        f"{called} cannot be called while an event loop is running. "
        f"Use `{instead}` instead."
    )


class Dispatchable:
    """Mixin that adds ``.dispatch()`` / ``.dispatch_after()`` to any Job class."""

    _connection: ClassVar[Optional[Any]] = None
    _queue_name: ClassVar[str] = "default"

    @classmethod
    async def dispatch(cls, *args: Any, **kwargs: Any) -> str:
        """Push the job onto its configured queue immediately.

        Pushing is an I/O operation against the queue backend, so this is a
        coroutine and must be awaited::

            job_id = await SendWelcomeEmail.dispatch("user-42")

        From synchronous code — a management command, a script — use
        :meth:`dispatch_blocking` instead.

        Returns:
            The job ID assigned by the queue connection.
        """
        return await cls.dispatch_after(0, *args, **kwargs)

    @classmethod
    async def dispatch_after(
        cls, delay: Annotated[int, Doc("Seconds to delay.")], *args: Any, **kwargs: Any
    ) -> str:
        """Push the job onto its queue after *delay* seconds.

        Returns:
            The job ID assigned by the queue connection.

        Raises:
            RuntimeError: If no queue connection has been configured.
        """
        payload = cls._encode_payload(args, kwargs)
        return await cls._require_connection().push(
            cls._queue_name, payload, delay=delay
        )

    @classmethod
    def dispatch_blocking(
        cls,
        *args: Any,
        delay: Annotated[int, Doc("Seconds to delay.")] = 0,
        **kwargs: Any,
    ) -> str:
        """Push the job onto its queue from synchronous code.

        Runs its own event loop, so it is only usable where none is already
        running. Inside a handler, a worker, or any other async context, await
        :meth:`dispatch` instead.

        Returns:
            The job ID assigned by the queue connection.

        Raises:
            RuntimeError: If called while an event loop is running, or if no
                queue connection has been configured.
        """
        return _run_blocking(
            cls.dispatch_after(delay, *args, **kwargs),
            f"{cls.__name__}.dispatch_blocking()",
            "await {}.dispatch(...)".format(cls.__name__),
        )

    @classmethod
    def _require_connection(cls) -> Any:
        """Return the configured queue connection or explain what is missing."""
        if cls._connection is None:
            raise RuntimeError(
                f"No queue connection configured for {cls.__name__}. "
                f"Call {cls.__name__}.on_connection(connection) first."
            )
        return cls._connection

    @classmethod
    def job_reference(cls) -> str:
        """How this job is named in the queue, so a worker can find it again.

        Fully qualified: the worker is a separate process that has to import
        the class before it can run it, and a bare class name says nothing
        about where to import it from.
        """
        return f"{cls.__module__}.{cls.__name__}"

    @classmethod
    def _encode_payload(cls, args: Any, kwargs: Any) -> str:
        """Serialise the dispatch arguments into the queue payload."""
        return json.dumps(
            {"job": cls.job_reference(), "args": list(args), "kwargs": kwargs},
            default=str,
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
        """Run the job inline in this process, bypassing the queue entirely.

        Runs its own event loop, so it is only usable from synchronous code.
        Inside an async context, await :meth:`perform_now` instead.

        Raises:
            RuntimeError: If called while an event loop is running.
        """
        return _run_blocking(
            cls.perform_now(*args, **kwargs),
            f"{cls.__name__}.dispatch_sync()",
            "await {}.perform_now(...)".format(cls.__name__),
        )

    @classmethod
    async def perform_now(cls, *args: Any, **kwargs: Any) -> Any:
        """Run the job inline, bypassing the queue.

        The async counterpart of :meth:`dispatch_sync`, for use from a handler
        or anywhere else an event loop is already running.
        """
        instance = cls(*args, **kwargs)
        return await instance.handle()  # ty: ignore[unresolved-attribute]


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
            "job": self.__class__.job_reference(),
            "maxTries": self.max_tries(),
            "timeout": self.timeout,
            "data": self.__dict__,
        }


async def dispatch(job_class: Type[Job], *args: Any, **kwargs: Any) -> str:
    """Convenience function to dispatch any Job subclass.

    Must be awaited, like :meth:`Job.dispatch` itself::

        job_id = await dispatch(SendWelcomeEmail, "user-42")
    """
    return await job_class.dispatch(*args, **kwargs)
