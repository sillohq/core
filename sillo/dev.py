"""The development server behind :command:`sillo dev`.

Uvicorn remains the ASGI transport.  This module owns the development
experience around it: discovery-friendly reload, a compact startup card and
one consistent request line for every HTTP response.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from .console import DANGER, INFO, MUTED, PRIMARY, SUCCESS, Output, Palette

__all__ = ["DevAccessLog", "DevReporter", "run_dev"]


ASGIApp = Callable[..., Awaitable[None]]
_TARGET_ENV = "SILLO_DEV_TARGET"


class DevReporter:
    """Write the small, readable server messages Sillo owns."""

    def __init__(self, output: Output | None = None) -> None:
        self.output = output or Output(sys.stdout, Palette(sys.stdout))

    def starting(
        self,
        target: str,
        host: str,
        port: int,
        reload: bool,
        application: Any | None = None,
    ) -> None:
        """Announce the server and the useful local links."""
        address = f"http://{host}:{port}"
        rows = [("app", target), ("local", address)]
        docs = getattr(application, "docs", None)
        if docs:
            rows.append(("docs", f"{address}{getattr(docs[0], 'path', '/docs')}"))
        rows.append(("reload", "on" if reload else "off"))

        self.output.panel(
            "\n".join(f"{label:<7} {value}" for label, value in rows),
            "SILLO DEV",
            PRIMARY,
        )
        self.output.muted("  Press Ctrl+C to stop.")

    def request(self, method: str, path: str, status: int, elapsed: float) -> None:
        """Write a completed HTTP request, colouring the status by outcome."""
        if status >= 500:
            style = DANGER
        elif status >= 400:
            style = INFO
        elif status >= 300:
            style = PRIMARY
        else:
            style = SUCCESS
        status_text = self.output.paint(str(status), style)
        self.output.line(
            f"  {method:<7} {status_text}  {path}  {elapsed * 1_000:.1f}ms",
            MUTED,
        )

    def server_error(self, message: str) -> None:
        """Report a server-level failure without Uvicorn's default prefix."""
        self.output.error(message)


class DevAccessLog:
    """ASGI middleware that records completed HTTP responses once."""

    def __init__(self, application: ASGIApp, reporter: DevReporter) -> None:
        self.application = application
        self.reporter = reporter

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.application(scope, receive, send)
            return

        started = time.perf_counter()
        status: int | None = None

        async def record_send(message: dict[str, Any]) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.application(scope, receive, record_send)
        finally:
            # An app that raises before emitting a response is still useful to
            # see in the request stream. The exception continues upward so
            # Sillo's error handler / Uvicorn can render it appropriately.
            raw_path = scope.get("path", "/")
            query = scope.get("query_string", b"")
            if query:
                raw_path = f"{raw_path}?{query.decode('latin-1')}"
            self.reporter.request(
                scope.get("method", "HTTP"),
                raw_path,
                status or 500,
                time.perf_counter() - started,
            )


class _ServerErrorHandler(logging.Handler):
    """Keep infrastructure errors visible while silencing Uvicorn chatter."""

    def __init__(self, reporter: DevReporter) -> None:
        super().__init__(logging.ERROR)
        self.reporter = reporter

    def emit(self, record: logging.LogRecord) -> None:
        self.reporter.server_error(record.getMessage())


def _import_target(target: str) -> Any:
    """Import *target* without importing the command module at import time."""
    from .__main__ import _import_string

    return _import_string(target)


def development_application() -> DevAccessLog:
    """Load and wrap the target in a reload child process.

    Uvicorn's reload supervisor accepts an import string, not an already
    imported app.  The environment carries the user's import target into that
    child; this factory is therefore a real reload boundary rather than a
    shell command which happens to pass ``--reload`` through.
    """
    target = os.environ.get(_TARGET_ENV)
    if not target:
        raise RuntimeError("SILLO_DEV_TARGET was not set for the reload process")
    return DevAccessLog(_import_target(target), DevReporter())


def _configure_server_logging(reporter: DevReporter) -> None:
    """Replace Uvicorn's generic access/startup logs with Sillo's output."""
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = False
        logger.setLevel(logging.ERROR)
    logging.getLogger("uvicorn.error").addHandler(_ServerErrorHandler(reporter))


def run_dev(
    target: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = True,
    reload_dirs: list[Path] | None = None,
    reporter: DevReporter | None = None,
) -> int:
    """Run a Sillo development server for an application import string."""
    import uvicorn

    reporter = reporter or DevReporter()
    _configure_server_logging(reporter)
    directories = [str(directory) for directory in (reload_dirs or [Path.cwd()])]

    # Validate an explicit target before a reload supervisor is started and use
    # the loaded application to expose an available documentation link.
    discovered = _import_target(target)
    application: Any | str
    if reload:
        # The target stays importable across the reloader's process boundary.
        application = "sillo.dev:development_application"
        previous_target = os.environ.get(_TARGET_ENV)
        os.environ[_TARGET_ENV] = target
    else:
        previous_target = None
        application = DevAccessLog(discovered, reporter)

    reporter.starting(target, host, port, reload, discovered)
    config = uvicorn.Config(
        application,
        host=host,
        port=port,
        reload=reload,
        reload_dirs=directories if reload else None,
        factory=reload,
        access_log=False,
        log_config=None,
        log_level="error",
    )
    server = uvicorn.Server(config)

    try:
        if config.should_reload:
            from uvicorn.supervisors import ChangeReload

            socket = config.bind_socket()
            ChangeReload(config, target=server.run, sockets=[socket]).run()
        else:
            server.run()
    except KeyboardInterrupt:
        return 0
    finally:
        if reload:
            if previous_target is None:
                os.environ.pop(_TARGET_ENV, None)
            else:
                os.environ[_TARGET_ENV] = previous_target

    return 0 if server.started or config.should_reload else 1
