"""Server-Sent Events.

SSE is a one-way channel from server to browser over an ordinary HTTP
response: the body never ends, and each event is a short block of
``field: value`` lines terminated by a blank line. The browser side is
``EventSource``, which reconnects on its own and replays from the last event
id it saw.

The wire format is unforgiving in ways that are easy to get wrong by hand — a
newline inside a value silently truncates the event, a payload containing a
line break needs one ``data:`` line per line, and a connection with nothing to
say gets closed by intermediaries after 30-60 seconds. This module handles
those, and :meth:`sillo.core.http.Response.sse` wires it to a response.

Typical use::

    @app.get("/events")
    async def events(request: Request, response: Response):
        async def source():
            while True:
                yield {"price": await next_tick()}

        return response.sse(source())

Yield whatever is convenient: a ``dict`` or list is JSON-encoded, a ``str`` is
sent as-is, and a :class:`ServerSentEvent` gives control over the event name,
id and reconnection hint.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterable, AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

__all__ = ["ServerSentEvent", "last_event_id", "sse_stream"]

#: What a keepalive looks like on the wire. A line beginning with a colon is a
#: comment: the spec requires clients to ignore it, so it costs the page
#: nothing while still being traffic, which is the point.
DEFAULT_PING = "ping"

#: Long enough not to be chatty, short enough to beat the common idle timeouts.
#: nginx's ``proxy_read_timeout`` and many load balancers default to 60s.
DEFAULT_KEEPALIVE = 15.0


def _encode_field(name: str, value: str) -> str:
    """Render one ``field: value`` line, or several for a multi-line value.

    A newline inside a value would terminate the field early and, if it were a
    blank line, the whole event — so a value spanning lines is emitted as one
    line per field, which is exactly how the spec says to send multi-line data.
    """
    return "".join(f"{name}: {line}\n" for line in value.split("\n"))


@dataclass(slots=True)
class ServerSentEvent:
    """One event, and the knobs the protocol actually has.

    Attributes:
        data: The payload. A ``str`` is sent unchanged; anything else is passed
            through the encoder (JSON by default).
        event: The event name, which is what ``addEventListener("name", …)``
            on the client selects. Omitted means the client's ``onmessage``.
        id: The event id. The browser sends the last one it saw back as the
            ``Last-Event-ID`` header when it reconnects, which is what makes
            resuming a stream possible — see :func:`last_event_id`.
        retry: How long the browser should wait before reconnecting, in
            milliseconds. Sent once is enough; the client remembers it.
        comment: A comment line. Ignored by clients, so it is what a keepalive
            is made of.
    """

    data: Any = None
    event: str | None = None
    id: str | None = None
    retry: int | None = None
    comment: str | None = None

    def encode(
        self, encoder: Callable[[Any], str] = json.dumps, charset: str = "utf-8"
    ) -> bytes:
        """Render this event in the wire format, terminated by a blank line.

        Args:
            encoder: Applied to ``data`` when it is not already a string.
            charset: The encoding of the returned bytes. SSE is always UTF-8
                in practice; the argument exists so the caller decides rather
                than this module assuming.

        Returns:
            The encoded event, ready to write to the body.

        Raises:
            ValueError: If ``id`` contains a newline or NUL, or ``retry`` is
                not a whole number of milliseconds. Both would corrupt the
                stream rather than fail visibly, so they are refused here.
        """
        parts: list[str] = []

        if self.comment is not None:
            # Written as ": text", the comment form, rather than "comment: ".
            parts.append("".join(f": {line}\n" for line in self.comment.split("\n")))

        if self.event is not None:
            parts.append(_encode_field("event", self.event))

        if self.id is not None:
            if "\n" in self.id or "\r" in self.id or "\0" in self.id:
                raise ValueError(
                    "An SSE id cannot contain a newline or NUL; the client would "
                    f"read a truncated value. Got {self.id!r}."
                )
            parts.append(_encode_field("id", self.id))

        if self.retry is not None:
            if not isinstance(self.retry, int) or isinstance(self.retry, bool):
                raise ValueError(
                    "An SSE retry must be an integer number of milliseconds; "
                    f"got {self.retry!r}. Clients ignore a non-integer value, "
                    "so a float here silently does nothing."
                )
            parts.append(f"retry: {self.retry}\n")

        if self.data is not None:
            payload = self.data if isinstance(self.data, str) else encoder(self.data)
            parts.append(_encode_field("data", payload))

        # The blank line is what ends the event. Without it the client holds
        # everything in its buffer and dispatches nothing.
        parts.append("\n")
        return "".join(parts).encode(charset)


def _coerce(item: Any) -> ServerSentEvent:
    """Accept the shapes a handler is likely to yield."""
    if isinstance(item, ServerSentEvent):
        return item
    return ServerSentEvent(data=item)


def last_event_id(request: Any) -> str | None:
    """The id the client last received, if this is a reconnection.

    ``EventSource`` reconnects on its own after a dropped connection and sends
    the last id it saw. A handler that reads this can resume from there instead
    of replaying the stream from the beginning.

    Args:
        request: The incoming request.

    Returns:
        The ``Last-Event-ID`` header, or None on a first connection.
    """
    return request.headers.get("last-event-id")


async def sse_stream(
    source: AsyncIterable[Any],
    *,
    keepalive: float | None = DEFAULT_KEEPALIVE,
    ping: str = DEFAULT_PING,
    retry: int | None = None,
    encoder: Callable[[Any], str] = json.dumps,
    charset: str = "utf-8",
) -> AsyncIterator[bytes]:
    """Wrap an async iterable into an encoded SSE body.

    Args:
        source: Yields events. Each item is a :class:`ServerSentEvent`, a
            ``str``, or anything the encoder handles.
        keepalive: Seconds of silence after which a comment is sent to hold
            the connection open. None disables it.
        ping: The comment text used for a keepalive.
        retry: Sent once, before anything else, as the client's reconnection
            delay in milliseconds.
        encoder: Applied to non-string payloads.
        charset: Encoding of the emitted bytes.

    Yields:
        Encoded events, and keepalive comments in the gaps between them.
    """
    if retry is not None:
        yield ServerSentEvent(retry=retry).encode(encoder, charset)

    iterator = source.__aiter__()
    pending: asyncio.Future[Any] | None = None

    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(iterator.__anext__())

            if keepalive is None:
                done_future = pending
            else:
                # asyncio.wait rather than wait_for: on timeout it leaves the
                # future running. wait_for would cancel it, losing whatever
                # event the source was in the middle of producing — the
                # keepalive would eat one event every time it fired.
                done, _ = await asyncio.wait({pending}, timeout=keepalive)
                if not done:
                    yield ServerSentEvent(comment=ping).encode(encoder, charset)
                    continue
                done_future = pending

            try:
                item = await done_future
            except StopAsyncIteration:
                break
            finally:
                pending = None

            yield _coerce(item).encode(encoder, charset)
    finally:
        # The client going away cancels the generator mid-await, so the
        # in-flight __anext__ and the source itself are closed here rather than
        # left pending — otherwise a disconnected browser leaves a task per
        # connection running until the process exits.
        if pending is not None and not pending.done():
            pending.cancel()
            # Cancellation is a request, not an event: the source is still
            # mid-__anext__ until it is awaited, and closing a generator that
            # is still running raises "asynchronous generator is already
            # running". Awaiting the cancelled future is what lets it unwind.
            try:
                await pending
            except (asyncio.CancelledError, StopAsyncIteration):
                pass

        aclose = getattr(iterator, "aclose", None)
        if aclose is not None:
            await aclose()
