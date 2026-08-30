"""A debug error page must describe the request that failed, and no other.

``ServerErrorMiddleware`` used to store the request on itself and read it back
while rendering. One instance serves every request — `use()` keeps the
instance, and the application assembles its chain once — so the attribute held
whichever request wrote to it last. Since the page renders every header it is
given, a request that failed slowly returned another request's ``Cookie`` and
``Authorization`` to the wrong client.

The whole suite is otherwise sequential, which is why nothing caught it: with
one request in flight there is never a second writer. These tests interleave
deliberately.
"""

import asyncio

import pytest

from sillo import SilloApp


def _app():
    app = SilloApp(debug=True)

    @app.get("/boom")
    async def boom(ctx):
        # The await is the point: it is a suspension, and a suspension is all
        # another request needs to overwrite shared state.
        await asyncio.sleep(float(ctx.query_params.get("delay", 0)))
        raise RuntimeError("kaboom")

    return app


def _scope(token, delay, accept=b"text/html"):
    return {
        "type": "http",
        "method": "GET",
        "path": "/boom",
        "raw_path": b"/boom",
        "query_string": f"delay={delay}".encode(),
        "headers": [
            (b"host", b"test"),
            (b"authorization", token.encode()),
            (b"accept", accept),
        ],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
        "scheme": "http",
        "http_version": "1.1",
        "root_path": "",
    }


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


async def _fetch(app, token, delay, accept=b"text/html"):
    chunks: list[bytes] = []

    async def send(message):
        if message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    await app(_scope(token, delay, accept), _receive, send)
    return b"".join(chunks).decode("utf-8", "replace")


def _headers_table(page):
    """Just the rendered request-headers block, which is what the bug fed."""
    start = page.find("<h3>Headers</h3>")
    return page[start : start + 4000] if start != -1 else ""


class TestConcurrentDebugPagesDoNotCross:
    async def test_a_slow_failure_does_not_render_another_requests_headers(self):
        app = _app()

        slow, quick = await asyncio.gather(
            _fetch(app, "Bearer SLOW-TOKEN", 0.05),
            _fetch(app, "Bearer QUICK-TOKEN", 0.001),
        )

        slow_headers = _headers_table(slow)
        assert slow_headers, "the debug page did not render a headers table"
        assert "SLOW-TOKEN" in slow_headers
        assert "QUICK-TOKEN" not in slow_headers

        quick_headers = _headers_table(quick)
        assert "QUICK-TOKEN" in quick_headers
        assert "SLOW-TOKEN" not in quick_headers

    async def test_it_holds_with_many_requests_in_flight(self):
        app = _app()

        # Staggered delays, so every request is suspended while others start
        # and finish around it.
        pages = await asyncio.gather(
            *(_fetch(app, f"Bearer TOKEN-{i}", i * 0.01) for i in range(8))
        )

        for i, page in enumerate(pages):
            headers = _headers_table(page)
            assert f"TOKEN-{i}" in headers, f"request {i} lost its own headers"
            others = [f"TOKEN-{j}" for j in range(8) if j != i]
            leaked = [t for t in others if t in headers]
            assert not leaked, f"request {i} rendered {leaked}"

    async def test_the_middleware_keeps_no_request_state(self):
        # The durable form of the guarantee: the fix is not that the attribute
        # is refreshed carefully, it is that there is no attribute.
        app = _app()
        await _fetch(app, "Bearer ANY", 0)

        chain = app._request_chain
        seen = set()
        node = chain
        while node is not None and id(node) not in seen:
            seen.add(id(node))
            dispatch = getattr(node, "dispatch_func", None)
            if dispatch is not None:
                assert not hasattr(dispatch, "current_request")
            node = getattr(node, "app", None)


class TestTheErrorPageStillWorks:
    async def test_html_is_returned_for_a_browser(self):
        page = await _fetch(_app(), "Bearer T", 0)
        assert "<h3>Headers</h3>" in page
        assert "kaboom" in page

    async def test_plain_text_is_returned_without_an_html_accept(self):
        page = await _fetch(_app(), "Bearer T", 0, accept=b"application/json")
        assert "kaboom" in page
        assert "<h3>Headers</h3>" not in page

    def test_generate_html_requires_a_request(self):
        from sillo.core.error import ServerErrorMiddleware

        with pytest.raises(TypeError):
            # Deliberately the old signature: an external caller that still
            # writes it must fail here rather than silently render whatever
            # request happened to be around.
            ServerErrorMiddleware(debug=True).generate_html(RuntimeError("x"))  # ty: ignore[missing-argument]
