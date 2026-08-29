"""The parts of ``HttpContext`` reached by inspection rather than by routing.

A request is a mapping over the ASGI scope, a body it can read exactly once,
and a handful of properties that answer questions about the connection. The
mapping protocol, the disconnect probe, the push-promise extension and the
error you get for reading a body twice are all real API, and all of them sit
outside the path a normal handler takes.
"""

from __future__ import annotations

import anyio
import pytest

from sillo.core.http.context import Address, HttpContext


def make_scope(**overrides):
    base = {
        "type": "http",
        "method": "GET",
        "path": "/here",
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "server": ("example.test", 80),
        "client": ("10.0.0.1", 51234),
    }
    base.update(overrides)
    return base


async def body_receive(*chunks: bytes):
    """A receive channel that yields *chunks* then stops."""
    messages = [
        {"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
        for index, chunk in enumerate(chunks)
    ] or [{"type": "http.request", "body": b"", "more_body": False}]
    iterator = iter(messages)

    async def receive():
        try:
            return next(iterator)
        except StopIteration:
            return {"type": "http.disconnect"}

    return receive


class TestTheMappingProtocol:
    """``HttpContext`` is a Mapping over the scope, which is what lets middleware
    read scope keys off the request without reaching for ``.scope``."""

    def test_a_key_is_readable(self):
        request = HttpContext(make_scope(), None)

        assert request["method"] == "GET"

    def test_a_missing_key_raises(self):
        request = HttpContext(make_scope(), None)

        with pytest.raises(KeyError):
            request["not-there"]

    def test_it_iterates_the_scope_keys(self):
        request = HttpContext(make_scope(), None)

        assert "method" in list(request)

    def test_it_has_the_scope_s_length(self):
        scope = make_scope()
        request = HttpContext(scope, None)

        assert len(request) == len(scope)

    def test_the_app_comes_off_the_scope(self):
        sentinel = object()
        request = HttpContext(make_scope(app=sentinel), None)

        assert request.app is sentinel


class TestTheClientAddress:
    def test_the_client_is_reported_as_an_address(self):
        request = HttpContext(make_scope(client=("10.0.0.1", 51234)), None)

        assert request.client == Address("10.0.0.1", 51234)

    def test_an_absent_client_is_none(self):
        """A request from a unix socket, or a test harness, has no peer."""
        request = HttpContext(make_scope(client=None), None)

        assert request.client is None


class TestHeaderConveniences:
    def test_the_origin_is_read_from_the_header(self):
        request = HttpContext(
            make_scope(headers=[(b"origin", b"https://other.test")]), None
        )

        assert request.origin == "https://other.test"

    def test_an_absent_origin_is_derived_from_the_url(self):
        """``HttpContext.origin`` falls back to scheme+authority rather than
        answering None, so a same-origin request compares equal to the
        origin a cross-origin one would have sent."""
        request = HttpContext(make_scope(), None)

        assert request.origin == "http://example.test"

    def test_no_content_type_header_reads_as_none(self):
        request = HttpContext(make_scope(), None)

        assert request.content_type is None

    def test_a_content_type_is_returned_without_its_parameters(self):
        request = HttpContext(
            make_scope(headers=[(b"content-type", b"text/html; charset=utf-8")]), None
        )

        assert request.content_type == "text/html"


class TestChannelsThatWereNeverProvided:
    """A ``HttpContext`` can be built from a scope alone -- exception handlers and
    tests both do it -- and then has nothing to read from or write to."""

    async def test_receiving_without_a_channel_says_so(self):
        request = HttpContext(make_scope())

        with pytest.raises(RuntimeError, match="No receive channel"):
            await request.receive()

    async def test_sending_a_push_without_a_channel_says_so(self):
        request = HttpContext(
            make_scope(extensions={"http.response.push": {}}),
        )

        with pytest.raises(RuntimeError, match="No send channel"):
            await request.send_push_promise("/style.css")


class TestReadingTheBody:
    async def test_the_body_is_returned(self):
        request = HttpContext(make_scope(method="POST"), await body_receive(b"hello"))

        assert await request.body == b"hello"

    async def test_a_cached_body_streams_again(self):
        """Once the body is read it is kept, so a second consumer -- an
        exception handler, a logging middleware -- gets it rather than a
        'stream consumed' error."""
        request = HttpContext(make_scope(method="POST"), await body_receive(b"hello"))
        await request.body

        chunks = [chunk async for chunk in request.stream()]

        assert b"".join(chunks) == b"hello"

    async def test_streaming_twice_without_caching_is_refused(self):
        """The channel is drained, so the second read would hang forever
        waiting for a body that has already gone past."""
        request = HttpContext(make_scope(method="POST"), await body_receive(b"hello"))
        async for _ in request.stream():
            pass

        with pytest.raises(RuntimeError, match="Stream consumed"):
            async for _ in request.stream():
                pass

    async def test_text_decodes_as_utf8(self):
        request = HttpContext(
            make_scope(method="POST"), await body_receive("café".encode())
        )

        assert await request.text == "café"

    async def test_undecodable_text_falls_back_to_latin1(self):
        """A body that is not valid UTF-8 still has to produce *something*:
        raising here turns a malformed request into a 500 rather than a 400.
        """
        request = HttpContext(make_scope(method="POST"), await body_receive(b"\xff\xfe"))

        assert await request.text == "\xff\xfe".encode("latin-1").decode("latin-1")


class TestDisconnectDetection:
    async def test_a_disconnect_message_is_noticed(self):
        async def receive():
            return {"type": "http.disconnect"}

        request = HttpContext(make_scope(), receive)

        assert await request.is_disconnected() is True

    async def test_a_still_open_connection_reads_as_connected(self):
        """The probe cancels itself rather than waiting: asking 'are you still
        there?' must not block a handler that is mid-response."""

        async def receive():
            await anyio.sleep(10)
            return {"type": "http.request", "body": b"", "more_body": False}

        request = HttpContext(make_scope(), receive)

        assert await request.is_disconnected() is False

    async def test_the_answer_is_remembered(self):
        calls = []

        async def receive():
            calls.append(1)
            return {"type": "http.disconnect"}

        request = HttpContext(make_scope(), receive)
        await request.is_disconnected()
        await request.is_disconnected()

        assert len(calls) == 1, "the disconnect probe re-read a closed channel"


class TestServerPush:
    async def test_a_push_is_sent_when_the_server_supports_it(self):
        sent = []

        async def send(message):
            sent.append(message)

        request = HttpContext(
            make_scope(extensions={"http.response.push": {}}, headers=[]),
            None,
            send,
        )

        await request.send_push_promise("/style.css")

        assert sent[0]["type"] == "http.response.push"
        assert sent[0]["path"] == "/style.css"

    async def test_relevant_request_headers_are_copied_onto_the_push(self):
        """The pushed response is fetched by the browser as though it had
        asked, so the headers that decide *which* representation it gets have
        to travel with it."""
        sent = []

        async def send(message):
            sent.append(message)

        request = HttpContext(
            make_scope(
                extensions={"http.response.push": {}},
                headers=[(b"accept-encoding", b"gzip")],
            ),
            None,
            send,
        )

        await request.send_push_promise("/style.css")

        names = [name for name, _ in sent[0]["headers"]]
        assert b"accept-encoding" in names

    async def test_nothing_is_sent_when_the_server_does_not_support_push(self):
        sent = []

        async def send(message):
            sent.append(message)

        request = HttpContext(make_scope(extensions={}), None, send)

        await request.send_push_promise("/style.css")

        assert sent == []
