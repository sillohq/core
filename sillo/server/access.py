"""Access logging with a duration attached.

uvicorn's access record carries the client address, the request line and the
status, and no timing — the protocol logs it at the moment the response starts
and never measures how long the handler took. A development server that cannot
tell you which endpoint is slow is missing the one thing you look at a log for.

So the server wraps the loaded application in :class:`AccessLog`, an ASGI layer
that times each request and emits the line itself. It sits outside everything
the application installs, so what it measures is what the client waited for.

It never interferes with the response: it does not buffer, does not rewrite
messages, and passes ``receive`` straight through. The only thing it adds is a
wrapper around ``send`` that notes the status on the way past.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from sillo.server import theme
from sillo.types import Message, Receive, Scope, Send

#: Width of the method column. "OPTIONS" is the longest method in common use.
_METHOD_WIDTH = 7

#: Longest path shown before it is shortened from the left. With the timestamp,
#: method, status and duration columns around it, this keeps a full line inside
#: 80 characters — the width a terminal is still allowed to be.
_PATH_WIDTH = 34


def _shorten(path: str, width: int = _PATH_WIDTH) -> str:
    """Shorten a path from the left, keeping the end.

    The tail of a path is the part that identifies the request; the prefix is
    usually shared by everything in a router, so dropping the front loses less.

    Args:
        path: The request path, query string included.
        width: The maximum width.

    Returns:
        The path, elided from the left if it was too long.
    """
    if len(path) <= width:
        return path
    return "…" + path[-(width - 1) :] if theme.UNICODE else "..." + path[-(width - 3) :]


class AccessLog:
    """Times each request and writes one access line.

    Attributes:
        app: The application being served.
        stream: Where lines are written. Defaults to stderr, matching the rest
            of the server's output so redirecting stdout does not split the log
            in half.
    """

    def __init__(self, app: Any, stream: Any = None) -> None:
        """Wrap *app* in access logging.

        Args:
            app: The loaded ASGI application. Typed loosely on purpose: what
                the server hands over may be a WSGI bridge or any other
                wrapper, and narrowing this would reject callables that work.
            stream: Destination stream, or ``None`` for stderr.
        """
        self.app = app
        self.stream = stream if stream is not None else sys.stderr

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve one connection, logging it if it is HTTP.

        Args:
            scope: The ASGI scope. Lifespan and websocket scopes pass through
                untouched; neither has a status or a duration in the sense this
                log reports.
            receive: Passed through unchanged.
            send: Wrapped only to observe the response status.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status = 0
        started = time.perf_counter()

        async def send_observing_status(message: Message) -> None:
            """Forward a message, noting the status when it goes past."""
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_observing_status)
        except BaseException:
            # The request still happened and still cost time. Logging it before
            # re-raising means a crash appears in the access log rather than
            # leaving a gap where the slow request was.
            self._write(scope, status or 500, time.perf_counter() - started)
            raise

        self._write(scope, status, time.perf_counter() - started)

    def _write(self, scope: Scope, status: int, elapsed: float) -> None:
        """Emit one access line.

        Args:
            scope: The request scope.
            status: The response status, or 500 if the application raised
                before sending one.
            elapsed: Seconds spent handling the request.
        """
        milliseconds = elapsed * 1000
        method = str(scope.get("method", "?")).ljust(_METHOD_WIDTH)

        path = str(scope.get("root_path", "")) + str(scope.get("path", ""))
        query = scope.get("query_string", b"")
        if query:
            path = f"{path}?{query.decode('latin-1')}"

        stamp = time.strftime("%H:%M:%S")
        duration = theme.format_duration(milliseconds)

        line = (
            f"  {theme.paint(stamp, theme.TIMESTAMP)}"
            f"  {theme.paint(method, theme.VALUE)}"
            f" {theme.paint(str(status), theme.status_style(status))}"
            f"  {_shorten(path).ljust(_PATH_WIDTH)}"
            f"  {theme.paint(duration.rjust(8), theme.duration_style(milliseconds))}"
        )

        try:
            self.stream.write(line + "\n")
            self.stream.flush()
        except (ValueError, OSError):
            # The stream closed underneath us during shutdown. A log line is
            # never worth taking the server down for.
            pass
