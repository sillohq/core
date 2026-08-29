"""Tests for sillo.work.dependency — DI providers for work components."""

from sillo import SilloApp
from sillo import json
from sillo.core.dependencies import Depend
from sillo.core.http import HttpContext
from sillo.testclient import TestClient
from sillo.work import setup_work
from sillo.work.dependency import scheduler, queue_connection, events


def test_scheduler_injection():
    """scheduler provider resolves from app.state."""
    app = SilloApp()
    work = setup_work(app)
    sched = work["scheduler"]

    @app.get("/scheduler")
    async def handler(request: HttpContext, s=Depend(scheduler)):
        assert s is sched
        return json({"ok": True})

    client = TestClient(app)
    resp = client.get("/scheduler")
    assert resp.status_code == 200


def test_queue_connection_injection():
    """queue_connection provider resolves from app.state."""
    app = SilloApp()
    work = setup_work(app)
    conn = work["connection"]

    @app.get("/queue")
    async def handler(request: HttpContext, c=Depend(queue_connection)):
        assert c is conn
        return json({"ok": True})

    client = TestClient(app)
    resp = client.get("/queue")
    assert resp.status_code == 200


def test_events_injection():
    """events provider resolves from app.state."""
    app = SilloApp()
    setup_work(app)

    @app.get("/events")
    async def handler(request: HttpContext, d=Depend(events)):
        assert d is not None
        return json({"ok": True})

    client = TestClient(app)
    resp = client.get("/events")
    assert resp.status_code == 200


def test_provider_raises_when_not_setup():
    """Provider returns None gracefully when not configured."""
    from sillo.work.dependency import _make_provider
    provider = _make_provider("nonexistent")

    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext, x=Depend(provider)):
        assert x is None
        return json({"ok": True})

    client = TestClient(app)
    resp = client.get("/test")
    assert resp.status_code == 200
