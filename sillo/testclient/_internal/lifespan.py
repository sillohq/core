"""Detached lifespan supervision for the test clients' async context managers.

pytest-asyncio resolves ``async def`` fixtures by driving setup and teardown
from different tasks on the same event loop. anyio cancel scopes (and the
task groups built on them) may only be exited by the task that entered them,
so a client that enters a task group in ``__aenter__`` and exits it in
``__aexit__`` blows up during fixture teardown with::

    RuntimeError: Attempted to exit cancel scope in a different task
    than it was entered in

The fix is structural: the lifespan runs inside one dedicated supervisor
task that hosts every cancel scope it needs, and the context-manager sides
only observe the supervisor through the event/exception handle below. The
supervisor is spawned detached (``loop.create_task`` on asyncio,
``trio.lowlevel.spawn_system_task`` on trio), so neither side of the context
manager owns a cancel scope spanning both.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

import anyio

try:  # pragma: no cover - trio is an optional backend, absent from CI
    from trio import lowlevel as _trio_lowlevel
except ImportError:  # pragma: no cover
    _trio_lowlevel = None


class LifespanTaskHandle:
    """Observable outcome of the detached lifespan supervisor task.

    The raw backend task is not awaitable from arbitrary tasks (trio forbids
    it outright), so completion is signalled by ``done`` and the supervisor's
    exception is captured here for ``result()`` to re-raise — the same
    contract ``asyncio.Task.result()`` gives the old task-group code.
    """

    def __init__(self) -> None:
        self.done = anyio.Event()
        self.exception: BaseException | None = None
        # `asyncio.Task.cancel()` returns bool, `trio`'s system-task cancel
        # scope returns None; the caller only ever needs the side effect.
        self._cancel: Callable[[], object] | None = None

    def result(self) -> None:
        """Re-raise the supervisor's exception, if it captured one."""
        if self.exception is not None:
            raise self.exception

    def cancel(self) -> None:
        """Cancel the supervisor unless it has already finished."""
        if not self.done.is_set() and self._cancel is not None:
            self._cancel()

    async def abort(self) -> None:
        """Cancel the supervisor and wait for it to settle, ignoring outcome."""
        self.cancel()
        await self.done.wait()


async def _supervise(
    coro: Coroutine[Any, Any, None], handle: LifespanTaskHandle
) -> None:
    """Run the lifespan coroutine, recording its outcome on ``handle``.

    BaseException (cancellation included) is captured rather than re-raised:
    a detached task that raises would log "exception was never retrieved"
    when the failure path that triggered the cancel never awaits it.
    """
    try:
        await coro
    except BaseException as exc:
        handle.exception = exc
    finally:
        handle.done.set()


def start_detached_task(coro: Coroutine[Any, Any, None]) -> LifespanTaskHandle:
    """Start ``coro`` as a task owned by no caller cancel scope."""
    handle = LifespanTaskHandle()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    raw: Any
    if loop is not None:
        raw = loop.create_task(_supervise(coro, handle))
    elif _trio_lowlevel is not None:  # pragma: no cover - trio not in CI
        raw = _trio_lowlevel.spawn_system_task(_supervise, coro, handle)
    else:  # pragma: no cover - any supported backend provides one of the above
        raise RuntimeError(
            "AsyncTestClient requires the asyncio or trio backend to run a "
            "lifespan as an async context manager."
        )
    # The bound method doubles as the strong reference keeping the task alive:
    # event loops hold only weak references to running tasks.
    handle._cancel = raw.cancel
    return handle


async def run_startup_handshake(
    handle: LifespanTaskHandle, wait_startup: Callable[[], Awaitable[None]]
) -> None:
    """Await ``wait_startup``, stopping a failed lifespan before propagating."""
    try:
        await wait_startup()
    except BaseException:
        await handle.abort()
        raise


async def run_shutdown_handshake(
    handle: LifespanTaskHandle, wait_shutdown: Callable[[], Awaitable[None]]
) -> None:
    """Await ``wait_shutdown``, then settle the supervisor task.

    On the happy path the handshake is what finishes the lifespan, so this
    just waits for ``done`` and re-raises any exception the supervisor hit
    after replying — the old task group surfaced those too. A supervisor
    still alive after a failed handshake is cancelled; its captured
    cancellation must not mask the handshake's own error.
    """
    cancelled = False
    try:
        await wait_shutdown()
    finally:
        if not handle.done.is_set():
            cancelled = True
            handle.cancel()
        await handle.done.wait()
    if not cancelled:
        handle.result()
