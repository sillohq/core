from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
from types import ModuleType

from sillo.console import Output, Palette, strip_ansi
from sillo.dev import (
    _TARGET_ENV,
    DevAccessLog,
    DevReporter,
    _ServerErrorHandler,
    development_application,
    run_dev,
)


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


def test_access_log_leaves_websockets_alone():
    called = []

    async def application(scope, receive, send):
        called.append(scope["type"])

    report, stream = reporter()

    asyncio.run(
        DevAccessLog(application, report)(
            {"type": "websocket"},
            lambda: None,
            lambda message: None,
        )
    )

    assert called == ["websocket"]
    assert stream.getvalue() == ""


def test_reporter_distinguishes_redirects_client_errors_and_server_errors():
    report, stream = reporter()

    report.request("GET", "/moved", 302, 0)
    report.request("GET", "/missing", 404, 0)
    report.request("GET", "/broken", 500, 0)
    report.server_error("could not bind port")

    written = strip_ansi(stream.getvalue())
    assert "302" in written
    assert "404" in written
    assert "500" in written
    assert "could not bind port" in written


def test_server_error_handler_uses_the_sillo_reporter():
    report, stream = reporter()
    handler = _ServerErrorHandler(report)

    handler.emit(logging.makeLogRecord({"msg": "server failed"}))

    assert "server failed" in strip_ansi(stream.getvalue())


def test_reload_factory_requires_and_wraps_the_configured_target(monkeypatch):
    monkeypatch.delenv(_TARGET_ENV, raising=False)

    try:
        development_application()
    except RuntimeError as error:
        assert "was not set" in str(error)
    else:  # pragma: no cover - protects the assertion from a faulty factory
        raise AssertionError("a target should be required")

    module = ModuleType("reload_test_application")

    async def application(scope, receive, send):
        return None

    module.app = application
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setenv(_TARGET_ENV, "reload_test_application:app")

    wrapped = development_application()

    assert isinstance(wrapped, DevAccessLog)
    assert wrapped.application is application


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


def test_run_dev_returns_failure_when_the_server_cannot_start(monkeypatch):
    module = ModuleType("failed_dev_application")

    async def application(scope, receive, send):
        return None

    module.app = application
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr("uvicorn.Server.run", lambda server: None)

    assert run_dev("failed_dev_application:app", reload=False) == 1


def test_run_dev_supervises_reload_and_restores_the_previous_target(
    monkeypatch, tmp_path
):
    module = ModuleType("reloadable_dev_application")

    async def application(scope, receive, send):
        return None

    module.app = application
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setenv(_TARGET_ENV, "previous:app")
    captured = {}

    class Reload:
        def __init__(self, config, target, sockets):
            captured["config"] = config
            captured["target"] = target
            captured["sockets"] = sockets

        def run(self):
            captured["environment"] = os.environ[_TARGET_ENV]

    monkeypatch.setattr("uvicorn.Config.bind_socket", lambda config: "socket")
    monkeypatch.setattr("uvicorn.supervisors.ChangeReload", Reload)

    assert (
        run_dev(
            "reloadable_dev_application:app",
            reload=True,
            reload_dirs=[tmp_path],
        )
        == 0
    )
    assert captured["config"].app == "sillo.dev:development_application"
    assert captured["config"].factory is True
    assert captured["config"].reload_dirs == [tmp_path]
    assert captured["environment"] == "reloadable_dev_application:app"
    assert os.environ[_TARGET_ENV] == "previous:app"


def test_run_dev_treats_ctrl_c_as_a_clean_reload_shutdown(monkeypatch):
    module = ModuleType("interrupted_dev_application")

    async def application(scope, receive, send):
        return None

    module.app = application
    monkeypatch.setitem(sys.modules, module.__name__, module)

    class InterruptedReload:
        def __init__(self, config, target, sockets):
            pass

        def run(self):
            raise KeyboardInterrupt

    monkeypatch.setattr("uvicorn.Config.bind_socket", lambda config: "socket")
    monkeypatch.setattr("uvicorn.supervisors.ChangeReload", InterruptedReload)

    assert run_dev("interrupted_dev_application:app", reload=True) == 0
    assert _TARGET_ENV not in os.environ
