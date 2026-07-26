"""Deep integration tests for sillo.work — real silloApp routes exercising
background tasks, the job queue, the event dispatcher, and the scheduler,
all wired via setup_work and consumed through the real subsystems.
"""

import asyncio
import json

from sillo import silloApp
from sillo.work.background.tasks import BackgroundTask
from sillo.core.dependencies import Depend
from sillo.core.http import Request, Response
from sillo.testclient import AsyncTestClient
from sillo.work import setup_work
from sillo.work.dependency import events, queue_connection, scheduler
from sillo.work.queue.payloads import PayloadSerializer
from sillo.work.queue.workers import QueueWorker, WorkerOptions

from tests.test_work.work_jobs import FLIGHTS, SENT_EMAILS, SendEmail


def _make_app():
    app = silloApp()
    setup_work(app)
    return app


async def test_route_launches_background_task_and_drains():
    app = _make_app()
    sink = []

    @app.post("/ingest")
    async def ingest(request: Request, response: Response):
        async def process(value: str):
            sink.append(value)

        BackgroundTask.run(process, request.query_params.get("v", "x"))
        return response.json({"ok": True})

    async with AsyncTestClient(app) as client:
        resp = await client.post("/ingest?v=hello")
        assert resp.status_code == 200
        # wait for the fire-and-forget task to complete
        for _ in range(50):
            if sink:
                break
            await asyncio.sleep(0.02)

    assert sink == ["hello"]


async def test_route_dispatches_job_consumed_by_worker():
    app = _make_app()
    conn = app.state["queue_connection"]
    ser = PayloadSerializer()
    SENT_EMAILS.clear()

    @app.post("/email")
    async def send_email(request: Request, response: Response):
        to = request.query_params.get("to", "nobody")
        payload = json.dumps(
            {
                "job": "tests.test_work.work_jobs.SendEmail",
                "data": {"to": to, "subject": "Route"},
            }
        )
        await conn.push("default", payload)
        return response.json({"ok": True})

    worker = QueueWorker(
        _manager_with(conn),
        ser,
        _mem_repo(),
        options=WorkerOptions(concurrency=1, sleep=0.05, queues=["default"]),
    )

    async with AsyncTestClient(app) as client:
        resp = await client.post("/email?to=route@test")
        assert resp.status_code == 200
        task = asyncio.create_task(worker.run())
        for _ in range(100):
            if SENT_EMAILS:
                break
            await asyncio.sleep(0.02)
        worker.stop()
        await task

    assert SENT_EMAILS == ["route@test:Route"]


async def test_route_fires_event_through_dispatcher():
    app = _make_app()
    from sillo.work.queue.events import EventDispatcher

    dispatcher: EventDispatcher = app.state["events"]
    seen = []

    from dataclasses import dataclass
    from sillo.work.queue.events import Event

    @dataclass
    class RoutePing(Event):
        who: str

    async def handler(ev: RoutePing):
        seen.append(ev.who)

    dispatcher.register(RoutePing, handler)

    @app.post("/ping")
    async def ping(request: Request, response: Response, d=Depend(events)):
        await d.dispatch(RoutePing(who=request.query_params.get("who", "anon")))
        return response.json({"ok": True})

    async with AsyncTestClient(app) as client:
        resp = await client.post("/ping?who=router")
        assert resp.status_code == 200

    assert seen == ["router"]


async def test_route_exposes_scheduler_stats_via_di():
    app = _make_app()

    @app.get("/scheduler-stats")
    async def stats(request: Request, response: Response, s=Depend(scheduler)):
        return response.json(s.stats.to_dict())

    async with AsyncTestClient(app) as client:
        resp = await client.get("/scheduler-stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "jobs_total" in body
        assert "uptime" in body


async def test_route_reads_queue_size_via_di():
    app = _make_app()
    conn = app.state["queue_connection"]
    await conn.push("default", "sample-payload")

    @app.get("/queue-size")
    async def size(request: Request, response: Response, c=Depend(queue_connection)):
        return response.json({"size": await c.size("default")})

    async with AsyncTestClient(app) as client:
        resp = await client.get("/queue-size")
        assert resp.status_code == 200
        assert resp.json()["size"] >= 1


def _manager_with(conn):
    from sillo.work.queue.connection import ConnectionManager

    mgr = ConnectionManager()
    mgr.add("default", conn)
    return mgr


def _mem_repo():
    from sillo.work.queue.failed import MemoryFailedRepository

    return MemoryFailedRepository()
