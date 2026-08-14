"""Server-Sent Events: the wire format, and the keepalive that shares it."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from types import SimpleNamespace

import pytest

from sillo import Request, Response, SilloApp
from sillo.http.sse import ServerSentEvent, last_event_id, sse_stream
from sillo.testclient import TestClient


async def _collect(stream) -> list[bytes]:
    return [chunk async for chunk in stream]


async def _from(*items):
    for item in items:
        yield item


class TestEncoding:
    """The wire format, which fails silently when it is wrong."""

    def test_a_bare_payload_is_json_and_ends_with_a_blank_line(self):
        assert ServerSentEvent(data={"n": 1}).encode() == b'data: {"n": 1}\n\n'

    def test_a_string_payload_is_sent_unchanged(self):
        # Not JSON-encoded — a str would come out wrapped in quotes.
        assert ServerSentEvent(data="hello").encode() == b"data: hello\n\n"

    def test_fields_are_ordered_and_all_present(self):
        event = ServerSentEvent(data="x", event="tick", id="7", retry=3000)
        assert event.encode() == b"event: tick\nid: 7\nretry: 3000\ndata: x\n\n"

    def test_a_multi_line_payload_becomes_one_data_line_per_line(self):
        # The reason this matters: an embedded newline would otherwise end the
        # field, and a blank line would end the whole event.
        assert ServerSentEvent(data="a\nb").encode() == b"data: a\ndata: b\n\n"

    def test_a_comment_is_a_leading_colon(self):
        assert ServerSentEvent(comment="ping").encode() == b": ping\n\n"

    def test_a_comment_carries_no_data_field(self):
        # A keepalive must not dispatch a message event on the client.
        assert b"data:" not in ServerSentEvent(comment="ping").encode()

    def test_an_id_containing_a_newline_is_refused(self):
        # Truncates the value on the client rather than erroring, so it is
        # caught here instead.
        with pytest.raises(ValueError, match="newline"):
            ServerSentEvent(data="x", id="a\nb").encode()

    def test_a_non_integer_retry_is_refused(self):
        # Clients ignore a non-integer retry, so a float silently does nothing.
        with pytest.raises(ValueError, match="integer"):
            ServerSentEvent(data="x", retry=1.5).encode()  # type: ignore[arg-type]

    def test_the_encoder_is_replaceable(self):
        compact = ServerSentEvent(data={"a": 1, "b": 2}).encode(
            encoder=lambda v: json.dumps(v, separators=(",", ":"))
        )
        assert compact == b'data: {"a":1,"b":2}\n\n'


class TestStream:
    @pytest.mark.asyncio
    async def test_it_encodes_each_item(self):
        chunks = await _collect(sse_stream(_from({"n": 0}, {"n": 1}), keepalive=None))
        assert chunks == [b'data: {"n": 0}\n\n', b'data: {"n": 1}\n\n']

    @pytest.mark.asyncio
    async def test_retry_is_emitted_once_before_anything_else(self):
        chunks = await _collect(
            sse_stream(_from("a", "b"), keepalive=None, retry=2000)
        )
        assert chunks[0] == b"retry: 2000\n\n"
        assert b"retry" not in b"".join(chunks[1:])

    @pytest.mark.asyncio
    async def test_events_pass_through_with_their_own_fields(self):
        chunks = await _collect(
            sse_stream(_from(ServerSentEvent(data="x", event="tick", id="1")), keepalive=None)
        )
        assert chunks == [b"event: tick\nid: 1\ndata: x\n\n"]


class TestKeepalive:
    """The part with a race in it."""

    @pytest.mark.asyncio
    async def test_a_silent_source_still_produces_traffic(self):
        async def slow():
            await asyncio.sleep(0.30)
            yield "late"

        chunks = await _collect(sse_stream(slow(), keepalive=0.05))

        assert chunks[-1] == b"data: late\n\n"
        assert chunks[:-1], "expected keepalives while the source was silent"
        assert set(chunks[:-1]) == {b": ping\n\n"}

    @pytest.mark.asyncio
    async def test_a_keepalive_never_swallows_an_event(self):
        """The reason `asyncio.wait` is used instead of `wait_for`.

        `wait_for` cancels the future it is waiting on when it times out. Here
        that future is the source's in-flight `__anext__`, so every keepalive
        would discard the event being produced. This asserts all of them
        arrive, in order, across many keepalive firings.
        """

        async def steady():
            for i in range(5):
                await asyncio.sleep(0.04)
                yield i

        chunks = await _collect(sse_stream(steady(), keepalive=0.01))

        data = [c for c in chunks if c != b": ping\n\n"]
        assert data == [f"data: {i}\n\n".encode() for i in range(5)]

    @pytest.mark.asyncio
    async def test_keepalive_can_be_disabled(self):
        async def slow():
            await asyncio.sleep(0.1)
            yield "only"

        assert await _collect(sse_stream(slow(), keepalive=None)) == [b"data: only\n\n"]

    @pytest.mark.asyncio
    async def test_the_ping_text_is_configurable(self):
        async def slow():
            await asyncio.sleep(0.15)
            yield "x"

        chunks = await _collect(sse_stream(slow(), keepalive=0.05, ping="keep-alive"))
        assert b": keep-alive\n\n" in chunks


class TestCleanup:
    @pytest.mark.asyncio
    async def test_closing_early_closes_the_source(self):
        """A disconnected client must not leave the source running."""
        closed = False

        async def source():
            nonlocal closed
            try:
                while True:
                    yield "tick"
                    await asyncio.sleep(0.01)
            finally:
                closed = True

        stream = sse_stream(source(), keepalive=None)
        assert await stream.__anext__() == b"data: tick\n\n"
        await stream.aclose()

        assert closed, "the source generator was left open"

    @pytest.mark.asyncio
    async def test_closing_mid_keepalive_leaves_no_pending_task(self):
        async def never():
            await asyncio.sleep(3600)
            yield "never"

        stream = sse_stream(never(), keepalive=0.01)
        assert await stream.__anext__() == b": ping\n\n"

        before = len(asyncio.all_tasks())
        await stream.aclose()
        await asyncio.sleep(0)

        assert len(asyncio.all_tasks()) <= before


class TestLastEventId:
    def test_it_reads_the_reconnection_header(self):
        request = SimpleNamespace(headers={"last-event-id": "42"})
        assert last_event_id(request) == "42"

    def test_it_is_none_on_a_first_connection(self):
        assert last_event_id(SimpleNamespace(headers={})) is None


class TestResponseSse:
    """`response.sse()` end to end.

    The test transport buffers the whole body, so these assert on *what* is
    sent, never on when. Incremental delivery cannot be observed here and is
    verified against a real server instead.
    """

    def test_it_sets_the_headers_a_stream_needs(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = SilloApp()

        @app.get("/events")
        async def events(request: Request, response: Response):
            async def source():
                yield {"n": 1}

            return response.sse(source(), keepalive=None)

        with test_client_factory(app) as client:
            resp = client.get("/events")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers["cache-control"] == "no-cache, no-transform"
        assert resp.headers["connection"] == "keep-alive"
        # Without this nginx buffers the response and delivers it in batches.
        assert resp.headers["x-accel-buffering"] == "no"
        # A length would make it a fixed body rather than a stream.
        assert "content-length" not in resp.headers

    def test_it_encodes_the_events(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = SilloApp()

        @app.get("/events")
        async def events(request: Request, response: Response):
            async def source():
                yield ServerSentEvent(data={"n": 0}, event="tick", id="0")
                yield "plain"

            return response.sse(source(), keepalive=None, retry=4000)

        with test_client_factory(app) as client:
            body = client.get("/events").text

        assert body == (
            "retry: 4000\n\n"
            'event: tick\nid: 0\ndata: {"n": 0}\n\n'
            "data: plain\n\n"
        )

    def test_caller_headers_win_over_the_defaults(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = SilloApp()

        @app.get("/events")
        async def events(request: Request, response: Response):
            async def source():
                yield "x"

            return response.sse(
                source(), keepalive=None, headers={"cache-control": "private"}
            )

        with test_client_factory(app) as client:
            assert client.get("/events").headers["cache-control"] == "private"

    def test_the_encoder_is_replaceable(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = SilloApp()

        @app.get("/events")
        async def events(request: Request, response: Response):
            async def source():
                yield {"b": 2, "a": 1}

            return response.sse(
                source(),
                keepalive=None,
                encoder=lambda v: json.dumps(v, sort_keys=True, separators=(",", ":")),
            )

        with test_client_factory(app) as client:
            assert client.get("/events").text == 'data: {"a":1,"b":2}\n\n'

    def test_a_handler_can_resume_from_the_last_event_id(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = SilloApp()

        @app.get("/events")
        async def events(request: Request, response: Response):
            since = last_event_id(request)

            async def source():
                yield {"since": since}

            return response.sse(source(), keepalive=None)

        with test_client_factory(app) as client:
            resp = client.get("/events", headers={"Last-Event-ID": "9"})

        assert resp.text == 'data: {"since": "9"}\n\n'
