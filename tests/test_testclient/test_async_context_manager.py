"""Regression tests: async context-manager clients across task boundaries.

pytest-asyncio resolves ``async def`` fixtures by driving setup and teardown
from different tasks on the same event loop. The clients previously entered
an anyio task group in ``__aenter__`` and exited it in ``__aexit__``, which
anyio rejects during fixture teardown with::

    RuntimeError: Attempted to exit cancel scope in a different task
    than it was entered in

The lifespan now runs in a detached supervisor task, so entering and exiting
the context manager from different tasks must work — both through real
pytest-asyncio fixtures and in the deterministic enter-here/exit-there form.
"""

from __future__ import annotations

import anyio
import pytest

from sillo import SilloApp
from sillo.testclient import AsyncTestClient, TestClient


def _raw_lifespan_app(*, fail_on: str):
    """An ASGI app whose lifespan raises directly.

    SilloApp itself converts lifespan hook errors into ``*.failed`` messages,
    so a raw app is needed to exercise the client's exception propagation.
    """

    async def app(scope, receive, send):
        if scope["type"] != "lifespan":
            return
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                if fail_on == "startup":
                    raise RuntimeError("boom-startup")
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                if fail_on == "shutdown":
                    raise RuntimeError("boom-shutdown")
                await send({"type": "lifespan.shutdown.complete"})
                return

    return app


@pytest.fixture
async def async_client_in_fixture():
    async with AsyncTestClient(SilloApp()) as client:
        yield client


@pytest.fixture
async def sync_client_in_async_fixture():
    async with TestClient(SilloApp()) as client:
        yield client


async def test_async_client_in_pytest_asyncio_fixture(async_client_in_fixture):
    response = await async_client_in_fixture.get("/does-not-exist")
    assert response.status_code == 404


async def test_sync_client_async_ctx_in_pytest_asyncio_fixture(
    sync_client_in_async_fixture,
):
    response = sync_client_in_async_fixture.get("/does-not-exist")
    assert response.status_code == 404


async def test_async_client_exited_in_different_task_than_entered():
    client = AsyncTestClient(SilloApp())
    entered = anyio.Event()

    async def enter_from_child_task() -> None:
        await client.__aenter__()
        entered.set()

    async with anyio.create_task_group() as tg:
        tg.start_soon(enter_from_child_task)
        await entered.wait()
        response = await client.get("/does-not-exist")
        assert response.status_code == 404
        # Exited from the parent task while __aenter__ ran in the child.
        await client.__aexit__(None, None, None)


async def test_sync_client_async_ctx_exited_in_different_task_than_entered():
    client = TestClient(SilloApp())
    entered = anyio.Event()

    async def enter_from_child_task() -> None:
        await client.__aenter__()
        entered.set()

    async with anyio.create_task_group() as tg:
        tg.start_soon(enter_from_child_task)
        await entered.wait()
        response = client.get("/does-not-exist")
        assert response.status_code == 404
        await client.__aexit__(None, None, None)


async def test_async_client_startup_failure_surfaced_and_task_settled():
    client = AsyncTestClient(_raw_lifespan_app(fail_on="startup"))
    with pytest.raises(RuntimeError, match="boom-startup"):
        await client.__aenter__()
    # The failed startup must have cancelled and reaped the supervisor.
    assert client.task.done.is_set()


async def test_async_client_shutdown_failure_surfaced_and_task_settled():
    client = AsyncTestClient(_raw_lifespan_app(fail_on="shutdown"))
    await client.__aenter__()
    with pytest.raises(RuntimeError, match="boom-shutdown"):
        await client.__aexit__(None, None, None)
    assert client.task.done.is_set()
