from __future__ import annotations

import asyncio
import io
import sys
from types import ModuleType

from sillo.console import Output, Palette, strip_ansi
from sillo.dev import DevAccessLog, DevReporter, run_dev


def reporter() -> tuple[DevReporter, io.StringIO]:
    stream = io.StringIO()
    return DevReporter(Output(stream, Palette(stream, enabled=False))), stream


def test_startup_card_includes_the_docs_url_when_the_app_has_docs():
    class Docs:
        path = "/reference"

    class App:
        def __init__(self) -> None:
            self.docs = [Docs()]

    report, stream = reporter()

    report.starting("main:app", "127.0.0.1", 8000, True, App())

    written = strip_ansi(stream.getvalue())
    assert "SILLO DEV" in written
    assert "http://127.0.0.1:8000/reference" in written
    assert "reload  on" in written


def test_access_log_reports_method_status_path_and_duration():
    async def application(scope, receive, send):
        await send({"type": "http.response.start", "status": 201, "headers": []})
        await send({"type": "http.response.body", "body": b"created"})

    report, stream = reporter()
    logged = DevAccessLog(application, report)
    sent = []

    async def receive():
        return {}

    async def send(message):
        sent.append(message)

    asyncio.run(
        logged(
            {
                "type": "http",
                "method": "POST",
                "path": "/items",
                "query_string": b"draft=1",
            },
            receive,
            send,
        )
    )

    written = strip_ansi(stream.getvalue())
    assert [message["type"] for message in sent] == [
        "http.response.start",
        "http.response.body",
    ]
    assert "POST" in written
    assert "201" in written
    assert "/items?draft=1" in written
    assert "ms" in written


def test_access_log_marks_an_unanswered_exception_as_a_server_error():
    async def application(scope, receive, send):
        raise RuntimeError("broken")

    report, stream = reporter()
    logged = DevAccessLog(application, report)

    async def receive():
        return {}

    async def send(message):
        return None

    try:
        asyncio.run(
            logged(
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/broken",
                    "query_string": b"",
                },
                receive,
                send,
            )
        )
    except RuntimeError as error:
        assert str(error) == "broken"
    else:  # pragma: no cover - protects the assertion from a faulty test double
        raise AssertionError("the application exception should escape")

    written = strip_ansi(stream.getvalue())
    assert "GET" in written
    assert "500" in written


def test_run_dev_builds_a_server_without_uvicorn_access_logging(monkeypatch):
    module = ModuleType("dev_test_application")

    async def application(scope, receive, send):
        return None

    module.app = application
    monkeypatch.setitem(sys.modules, module.__name__, module)
    captured = {}

    def run(server):
        captured["config"] = server.config
        server.started = True

    monkeypatch.setattr("uvicorn.Server.run", run)
    report, _ = reporter()

    assert run_dev("dev_test_application:app", reload=False, reporter=report) == 0
    assert captured["config"].access_log is False
    assert isinstance(captured["config"].app, DevAccessLog)
