"""Access logging with a duration attached, and a link to the details.

uvicorn's access record carries the client address, the request line and the
status, and no timing — the protocol logs it at the moment the response starts
and never measures how long the handler took. A development server that cannot
tell you which endpoint is slow is missing the one thing you look at a log for.

So the server wraps the loaded application in :class:`AccessLog`, an ASGI layer
that times each request and emits the line itself. It sits outside everything
the application installs, so what it measures is what the client waited for.

When the request inspector is running, each line is also an ``OSC 8``
hyperlink: clicking the path in a terminal that supports it opens the full
record — both sets of headers, the query parameters, the client, the response
size. One line per request in the terminal, and the detail one click away
rather than crammed into it.

It never interferes with the response: it does not buffer, does not rewrite
messages, and passes ``receive`` straight through. The only thing it adds is a
wrapper around ``send`` that notes the response on the way past.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from sillo.console.terminal import hyperlink
from sillo.server import theme
from sillo.server.inspector import MOUNT, RequestLog, RequestRecord
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


def _decode(raw: Any) -> list[tuple[str, str]]:
    """Decode ASGI header pairs for display.

    Args:
        raw: Header pairs as ASGI carries them, or anything falsy.

    Returns:
        The same pairs as text. Latin-1 because that is what the HTTP spec says
        header bytes are, and because it cannot raise — a decode error here
        would take down a request over a log line.
    """
    return [
        (name.decode("latin-1"), value.decode("latin-1")) for name, value in raw or []
    ]


class AccessLog:
    """Times each request, records it, and writes one access line.

    Attributes:
        app: The application being served.
        stream: Where lines are written. Defaults to stderr, matching the rest
            of the server's output so redirecting stdout does not split the log
            in half.
        log: The inspector's ring buffer, or ``None`` when the inspector is not
            running — in which case nothing is recorded and the line is plain
            text rather than a link.
        base_url: The server's own root, used to build link targets.
    """

    def __init__(
        self,
        app: Any,
        stream: Any = None,
        log: RequestLog | None = None,
        base_url: str = "",
    ) -> None:
        """Wrap *app* in access logging.

        Args:
            app: The loaded ASGI application. Typed loosely on purpose: what
                the server hands over may be a WSGI bridge or any other
                wrapper, and narrowing this would reject callables that work.
            stream: Destination stream, or ``None`` for stderr.
            log: The inspector's ring buffer, when the inspector is mounted.
            base_url: The server's root URL, for building link targets.
        """
        self.app = app
        self.stream = stream if stream is not None else sys.stderr
        self.log = log
        self.base_url = base_url.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve one connection, logging it if it is HTTP.

        Args:
            scope: The ASGI scope. Lifespan and websocket scopes pass through
                untouched; neither has a status or a duration in the sense this
                log reports.
            receive: Passed through unchanged.
            send: Wrapped only to observe the response.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # The inspector's own pages are not requests the developer made, and
        # logging them would bury the ones that were.
        if str(scope.get("path", "")).startswith(MOUNT):
            await self.app(scope, receive, send)
            return

        status = 0
        response_headers: list[tuple[str, str]] = []
        response_bytes = 0
        started = time.perf_counter()
        started_at = time.time()

        async def send_observing(message: Message) -> None:
            """Forward a message, noting what the response is made of."""
            nonlocal status, response_headers, response_bytes
            if message["type"] == "http.response.start":
                status = message["status"]
                response_headers = _decode(message.get("headers", []))
            elif message["type"] == "http.response.body":
                response_bytes += len(message.get("body", b"") or b"")
            await send(message)

        try:
            await self.app(scope, receive, send_observing)
        except BaseException as exception:
            # The request still happened and still cost time. Recording it
            # before re-raising puts the crash in the log and in the inspector,
            # rather than leaving a gap where the interesting request was.
            self._finish(
                scope,
                status or 500,
                time.perf_counter() - started,
                started_at,
                response_headers,
                response_bytes,
                f"{type(exception).__name__}: {exception}",
            )
            raise

        self._finish(
            scope,
            status,
            time.perf_counter() - started,
            started_at,
            response_headers,
            response_bytes,
            "",
        )

    def _finish(
        self,
        scope: Scope,
        status: int,
        elapsed: float,
        started_at: float,
        response_headers: list[tuple[str, str]],
        response_bytes: int,
        error: str,
    ) -> None:
        """Record the request, then write its line.

        Args:
            scope: The request scope.
            status: The response status, or 500 if the application raised.
            elapsed: Seconds spent handling the request.
            started_at: Unix timestamp when handling began.
            response_headers: Headers the application sent.
            response_bytes: Body bytes sent.
            error: The exception description, when there was one.
        """
        milliseconds = elapsed * 1000
        path = str(scope.get("root_path", "")) + str(scope.get("path", ""))
        query = (scope.get("query_string", b"") or b"").decode("latin-1")

        record_id = 0
        if self.log is not None:
            record_id = self.log.next_id()
            client = scope.get("client")
            self.log.add(
                RequestRecord(
                    id=record_id,
                    method=str(scope.get("method", "?")),
                    path=path,
                    query=query,
                    status=status,
                    duration_ms=milliseconds,
                    started_at=started_at,
                    request_headers=_decode(scope.get("headers")),
                    response_headers=response_headers,
                    client=f"{client[0]}:{client[1]}" if client else "",
                    http_version=str(scope.get("http_version", "1.1")),
                    scheme=str(scope.get("scheme", "http")),
                    response_bytes=response_bytes,
                    error=error,
                )
            )

        self._write(scope, status, milliseconds, path, query, record_id)

    def _write(
        self,
        scope: Scope,
        status: int,
        milliseconds: float,
        path: str,
        query: str,
        record_id: int = 0,
    ) -> None:
        """Emit one access line.

        Args:
            scope: The request scope.
            status: The response status.
            milliseconds: How long the request took.
            path: The request path.
            query: The raw query string.
            record_id: The inspector record's id, or 0 when not recording.
        """
        full_path = f"{path}?{query}" if query else path
        method = str(scope.get("method", "?")).ljust(_METHOD_WIDTH)
        shown = _shorten(full_path).ljust(_PATH_WIDTH)

        if record_id and self.base_url:
            # Padded before it is linked: the escape sequence has no printable
            # width, so padding afterwards would count it and break the column.
            shown = hyperlink(f"{self.base_url}{MOUNT}/{record_id}", shown, self.stream)

        stamp = time.strftime("%H:%M:%S")
        duration = theme.format_duration(milliseconds)

        line = (
            f"  {theme.paint(stamp, theme.TIMESTAMP)}"
            f"  {theme.paint(method, theme.VALUE)}"
            f" {theme.paint(str(status), theme.status_style(status))}"
            f"  {shown}"
            f"  {theme.paint(duration.rjust(8), theme.duration_style(milliseconds))}"
        )

        try:
            self.stream.write(line + "\n")
            self.stream.flush()
        except (ValueError, OSError):
            # The stream closed underneath us during shutdown. A log line is
            # never worth taking the server down for.
            pass
