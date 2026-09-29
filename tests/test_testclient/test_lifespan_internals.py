"""Direct, deterministic unit tests for the ``wait_startup``/``wait_shutdown``
failure-message plumbing on TestClient/AsyncTestClient.

Driving this through a real ASGI app's full lifespan protocol is deadlock-prone:
once startup fails, sillo's own lifespan handler returns for good, so a
subsequent shutdown handshake (as triggered by ``__exit__``/``__aexit__``) would
wait forever for a reply that will never come. These tests instead seed the
internal streams directly and call the wait_* coroutines in isolation, which
exercises the same message-handling branches without needing a live app,
portal, or task group.
"""

from __future__ import annotations

import math

import anyio
import pytest
from anyio.streams.stapled import StapledObjectStream

from sillo.testclient import AsyncTestClient, TestClient
from sillo.testclient._internal import lifespan as _lifespan_module
from sillo.testclient._internal.lifespan import (
    LifespanTaskHandle,
    run_shutdown_handshake,
    start_detached_task,
)


class _DummyTask:
    """Stands in for the real Future/task object; always "succeeds".

    Deliberately duck-typed rather than a real ``Future`` or
    ``LifespanTaskHandle`` — assigning it to ``client.task`` below needs
    ``ty: ignore[invalid-assignment]`` for exactly that reason.
    """

    def result(self):
        return None


def _make_streams():
    send1, receive1 = anyio.create_memory_object_stream(math.inf)
    send2, receive2 = anyio.create_memory_object_stream(math.inf)
    return StapledObjectStream(send1, receive1), StapledObjectStream(send2, receive2)


async def _noop_app(scope, receive, send):
    pass  # pragma: no cover - never actually invoked in these tests


async def test_sync_client_wait_startup_failure_then_none():
    client = TestClient(_noop_app)
    client.stream_receive, client.stream_send = _make_streams()
    client.task = _DummyTask()  # ty: ignore[invalid-assignment]

    await client.stream_send.send({"type": "lifespan.startup.failed", "message": "x"})
    await client.stream_send.send(None)

    await client.wait_startup()

    startup_msg = await client.stream_receive.receive()
    assert startup_msg == {"type": "lifespan.startup"}


async def test_sync_client_wait_shutdown_failure_then_none_sync_mode():
    client = TestClient(_noop_app)
    client.stream_receive, client.stream_send = _make_streams()
    client.task = _DummyTask()  # ty: ignore[invalid-assignment]
    # wait_shutdown() picks its message-handling branch from the task type:
    # a DummyTask stands in for the sync portal future.
    assert not isinstance(client.task, LifespanTaskHandle)

    await client.stream_send.send({"type": "lifespan.shutdown.failed", "message": "x"})
    await client.stream_send.send(None)

    await client.wait_shutdown()


async def test_sync_client_wait_shutdown_failure_then_none_async_ctx_mode():
    client = TestClient(_noop_app)
    client.stream_receive, client.stream_send = _make_streams()
    # The detached-supervisor handle selects wait_shutdown()'s async-context
    # branch, as `async with TestClient(...)` does.
    client.task = LifespanTaskHandle()

    await client.stream_send.send({"type": "lifespan.shutdown.failed", "message": "x"})
    await client.stream_send.send(None)

    await client.wait_shutdown()


async def test_async_client_wait_startup_failure_then_none():
    client = AsyncTestClient(_noop_app)
    client.stream_receive, client.stream_send = _make_streams()
    client.task = _DummyTask()  # ty: ignore[invalid-assignment]

    await client.stream_send.send({"type": "lifespan.startup.failed", "message": "x"})
    await client.stream_send.send(None)

    await client.wait_startup()


async def test_async_client_wait_shutdown_failure_then_none():
    client = AsyncTestClient(_noop_app)
    client.stream_receive, client.stream_send = _make_streams()
    client.task = _DummyTask()  # ty: ignore[invalid-assignment]

    await client.stream_send.send({"type": "lifespan.shutdown.failed", "message": "x"})
    await client.stream_send.send(None)

    await client.wait_shutdown()


def test_start_detached_task_without_a_running_loop_or_trio_raises(monkeypatch):
    """``start_detached_task`` is synchronous and may be called with no
    asyncio loop running. Without trio available either, it must fail
    clearly rather than silently drop the lifespan coroutine."""
    monkeypatch.setattr(_lifespan_module, "_trio_lowlevel", None)

    async def noop() -> None:
        return None

    coro = noop()
    try:
        with pytest.raises(RuntimeError, match="requires the asyncio or trio backend"):
            start_detached_task(coro)
    finally:
        coro.close()


async def test_run_shutdown_handshake_reraises_supervisor_exception_after_clean_reply():
    """The supervisor can capture an exception from code that runs *after*
    it has already answered ``lifespan.shutdown.complete`` (cleanup in a
    ``finally``, say) — ``wait_shutdown`` then returns with no error of its
    own, and the handshake must still surface what the supervisor caught
    rather than swallow it once ``done`` is set."""
    handle = LifespanTaskHandle()
    handle.exception = RuntimeError("boom-after-reply")
    handle.done.set()

    async def wait_shutdown() -> None:
        return None

    with pytest.raises(RuntimeError, match="boom-after-reply"):
        await run_shutdown_handshake(handle, wait_shutdown)
