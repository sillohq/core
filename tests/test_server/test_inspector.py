"""The clickable request inspector.

Each access line the development server prints is an OSC 8 hyperlink to a page
served by the same process, showing what that request actually was.

The security tests here are the important ones. The inspector renders every
header a request arrived with, which includes session cookies and bearer
tokens, so two things have to hold and keep holding: it does not mount on an
address other machines can reach, and it never prints a credential in full.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from sillo.console.terminal import hyperlink
from sillo.server.access import AccessLog
from sillo.server.inspector import (
    MOUNT,
    Inspector,
    RequestLog,
    RequestRecord,
    is_loopback,
    redact,
    render_detail,
    render_index,
)


def _record(**overrides) -> RequestRecord:
    """Build a record with sensible defaults."""
    defaults = dict(
        id=1,
        method="GET",
        path="/users/42",
        query="page=2",
        status=200,
        duration_ms=12.5,
        started_at=1_700_000_000.0,
    )
    defaults.update(overrides)
    return RequestRecord(**defaults)


async def _call(app, scope):
    """Drive an ASGI app and return (status, body)."""
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    status = next(m["status"] for m in messages if m["type"] == "http.response.start")
    body = b"".join(
        m.get("body", b"") for m in messages if m["type"] == "http.response.body"
    )
    return status, body


def _scope(path, method="GET", query=b"", headers=None):
    return {
        "type": "http",
        "method": method,
        "path": path,
        "root_path": "",
        "query_string": query,
        "headers": headers or [],
        "client": ("127.0.0.1", 51234),
        "http_version": "1.1",
        "scheme": "http",
    }


class TestRedaction:
    """A credential must never be rendered in full."""

    @pytest.mark.parametrize(
        "header",
        ["authorization", "Authorization", "COOKIE", "set-cookie", "x-api-key"],
    )
    def test_sensitive_headers_are_cut_short(self, header):
        secret = "Bearer super-secret-token-abcdef1234567890"

        shown = redact(header, secret)

        assert secret not in shown
        assert "redacted" in shown

    def test_enough_prefix_survives_to_tell_tokens_apart(self):
        # Safe is not the only requirement: the point of the inspector is to
        # answer "which credential did this request carry".
        shown = redact("authorization", "Bearer aaaa-token")

        assert shown.startswith("Bearer a")
        assert "17 chars" in shown

    def test_ordinary_headers_are_untouched(self):
        assert redact("accept", "application/json") == "application/json"

    def test_an_empty_secret_says_so(self):
        assert redact("authorization", "") == "(empty)"

    def test_a_rendered_page_does_not_contain_the_token(self):
        record = _record(
            request_headers=[
                ("authorization", "Bearer super-secret-token-abcdef"),
                ("cookie", "session=deadbeefcafe"),
            ]
        )

        page = render_detail(record).decode()

        assert "super-secret-token-abcdef" not in page
        assert "deadbeefcafe" not in page
        assert "redacted" in page


class TestTheLoopbackGuard:
    @pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
    def test_loopback_addresses_are_allowed(self, host):
        assert is_loopback(host) is True

    @pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "::", "10.0.0.4"])
    def test_everything_else_is_not(self, host):
        # 0.0.0.0 is every interface, which is the case that matters: it is
        # what someone types to reach the dev server from their phone, and it
        # is exactly when publishing headers would be a leak.
        assert is_loopback(host) is False


class TestTheRing:
    def test_it_discards_the_oldest(self):
        log = RequestLog(capacity=3)
        for _ in range(5):
            log.add(_record(id=log.next_id()))

        assert len(log.all()) == 3

    def test_it_returns_newest_first(self):
        log = RequestLog()
        for _ in range(3):
            log.add(_record(id=log.next_id()))

        assert [r.id for r in log.all()] == [3, 2, 1]

    def test_ids_do_not_repeat_after_eviction(self):
        log = RequestLog(capacity=2)
        for _ in range(4):
            log.add(_record(id=log.next_id()))

        assert [r.id for r in log.all()] == [4, 3]

    def test_an_evicted_record_is_gone(self):
        log = RequestLog(capacity=1)
        log.add(_record(id=log.next_id()))
        log.add(_record(id=log.next_id()))

        assert log.get(1) is None
        assert log.get(2) is not None


class TestThePages:
    def test_the_index_lists_requests(self):
        log = RequestLog()
        log.add(_record(id=1, path="/alpha"))
        log.add(_record(id=2, path="/beta", status=404))

        page = render_index(log).decode()

        assert "/alpha" in page
        assert "/beta" in page
        assert "404" in page

    def test_an_empty_index_says_so_rather_than_showing_a_bare_table(self):
        assert "No requests yet" in render_index(RequestLog()).decode()

    def test_the_detail_page_shows_the_metadata(self):
        record = _record(
            client="10.0.0.1:5000",
            response_bytes=2048,
            response_headers=[("content-type", "application/json")],
        )

        page = render_detail(record).decode()

        assert "10.0.0.1:5000" in page
        assert "2,048 bytes" in page
        assert "application/json" in page
        assert "12.5ms" in page

    def test_query_parameters_are_broken_out(self):
        page = render_detail(_record(query="page=2&q=hello")).decode()

        assert "page" in page
        assert "hello" in page

    def test_an_unhandled_exception_is_shown(self):
        page = render_detail(_record(error="RuntimeError: kaboom")).decode()

        assert "kaboom" in page
        assert "Unhandled exception" in page

    def test_a_path_cannot_inject_markup(self):
        # The path comes from the client, so it is attacker-controlled input
        # rendered into a page the developer opens.
        page = render_detail(_record(path="/<script>alert(1)</script>")).decode()

        assert "<script>alert(1)</script>" not in page
        assert "&lt;script&gt;" in page

    def test_a_header_value_cannot_inject_markup(self):
        record = _record(request_headers=[("x-note", "<img src=x onerror=alert(1)>")])

        page = render_detail(record).decode()

        assert "<img src=x" not in page


class TestServingTheInspector:
    def test_the_index_is_served(self):
        log = RequestLog()
        log.add(_record(id=log.next_id()))

        async def app(scope, receive, send):
            raise AssertionError("the application should not see this")

        status, body = asyncio.run(_call(Inspector(app, log), _scope(MOUNT)))

        assert status == 200
        assert b"requests" in body

    def test_a_record_is_served_by_id(self):
        log = RequestLog()
        log.add(_record(id=log.next_id(), path="/findme"))

        async def app(scope, receive, send):
            raise AssertionError("the application should not see this")

        status, body = asyncio.run(_call(Inspector(app, log), _scope(f"{MOUNT}/1")))

        assert status == 200
        assert b"/findme" in body

    def test_a_missing_record_is_a_404_that_explains_itself(self):
        async def app(scope, receive, send):
            raise AssertionError("the application should not see this")

        status, body = asyncio.run(
            _call(Inspector(app, RequestLog()), _scope(f"{MOUNT}/999"))
        )

        assert status == 404
        assert b"ring buffer" in body

    def test_a_non_numeric_id_is_a_404_rather_than_a_crash(self):
        async def app(scope, receive, send):
            raise AssertionError("the application should not see this")

        status, _ = asyncio.run(
            _call(Inspector(app, RequestLog()), _scope(f"{MOUNT}/not-a-number"))
        )

        assert status == 404

    def test_json_is_available_for_tooling(self):
        log = RequestLog()
        log.add(_record(id=log.next_id(), path="/api/thing", query="", status=201))

        async def app(scope, receive, send):
            raise AssertionError("the application should not see this")

        status, body = asyncio.run(_call(Inspector(app, log), _scope(f"{MOUNT}/json")))
        payload = json.loads(body)

        assert status == 200
        assert payload[0]["path"] == "/api/thing"
        assert payload[0]["status"] == 201

    def test_everything_else_reaches_the_application(self):
        seen = []

        async def app(scope, receive, send):
            seen.append(scope["path"])
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        asyncio.run(_call(Inspector(app, RequestLog()), _scope("/users")))

        assert seen == ["/users"]

    def test_its_pages_are_not_cached_or_framed(self):
        log = RequestLog()
        log.add(_record(id=log.next_id()))
        messages = []

        async def app(scope, receive, send):
            raise AssertionError("unreachable")

        async def receive():
            return {"type": "http.request"}

        async def send(message):
            messages.append(message)

        asyncio.run(Inspector(app, log)(_scope(MOUNT), receive, send))
        headers = dict(messages[0]["headers"])

        assert headers[b"cache-control"] == b"no-store"
        assert headers[b"x-frame-options"] == b"DENY"


class TestTheAccessLogRecords:
    def test_a_request_is_recorded_with_its_headers_and_timing(self):
        import io

        log = RequestLog()

        async def app(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send(
                {"type": "http.response.body", "body": b"hello", "more_body": False}
            )

        wrapped = AccessLog(app, stream=io.StringIO(), log=log, base_url="http://x")
        asyncio.run(
            _call(wrapped, _scope("/thing", headers=[(b"accept", b"application/json")]))
        )

        record = log.all()[0]
        assert record.method == "GET"
        assert record.status == 200
        assert record.duration_ms > 0
        assert ("accept", "application/json") in record.request_headers
        assert ("content-type", "application/json") in record.response_headers
        assert record.response_bytes == 5
        assert record.client == "127.0.0.1:51234"

    def test_a_crash_is_recorded_with_its_exception(self):
        import io

        log = RequestLog()

        async def app(scope, receive, send):
            raise RuntimeError("kaboom")

        wrapped = AccessLog(app, stream=io.StringIO(), log=log, base_url="http://x")

        with pytest.raises(RuntimeError):
            asyncio.run(_call(wrapped, _scope("/boom")))

        record = log.all()[0]
        assert record.status == 500
        assert "kaboom" in record.error

    def test_the_inspectors_own_pages_are_not_logged(self):
        # Otherwise opening the inspector fills the inspector.
        import io

        log = RequestLog()
        stream = io.StringIO()

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        wrapped = AccessLog(app, stream=stream, log=log, base_url="http://x")
        asyncio.run(_call(wrapped, _scope(f"{MOUNT}/1")))

        assert log.all() == []
        assert stream.getvalue() == ""

    def test_the_line_links_to_the_record(self, monkeypatch):
        import io

        monkeypatch.setenv("SILLO_HYPERLINKS", "1")
        log = RequestLog()

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        stream = io.StringIO()
        wrapped = AccessLog(
            app, stream=stream, log=log, base_url="http://127.0.0.1:8000"
        )
        asyncio.run(_call(wrapped, _scope("/thing")))

        assert f"{MOUNT}/1" in stream.getvalue()
        assert "\x1b]8;;" in stream.getvalue()

    def test_without_an_inspector_the_line_is_plain(self, monkeypatch):
        import io

        monkeypatch.setenv("SILLO_HYPERLINKS", "1")

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        stream = io.StringIO()
        asyncio.run(_call(AccessLog(app, stream=stream), _scope("/thing")))

        assert "\x1b]8;;" not in stream.getvalue()


class TestHyperlinkRendering:
    def test_a_terminal_that_cannot_take_them_gets_plain_text(self, monkeypatch):
        monkeypatch.setenv("SILLO_HYPERLINKS", "0")

        assert hyperlink("http://x", "label") == "label"

    def test_the_sequence_wraps_the_label(self, monkeypatch):
        monkeypatch.setenv("SILLO_HYPERLINKS", "1")

        rendered = hyperlink("http://x/1", "label")

        assert rendered.startswith("\x1b]8;;http://x/1")
        assert "label" in rendered
        assert rendered.endswith("\x1b]8;;\x1b\\")
