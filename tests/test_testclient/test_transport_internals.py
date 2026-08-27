"""Direct unit tests for TestClientTransport/AsyncTestClientTransport edge cases
that public TestClient usage in the rest of the suite doesn't reach: explicit
ports, missing Host headers, ASGI conformance violations, and debug template
propagation.
"""

from __future__ import annotations

import pytest

from sillo.testclient import AsyncTestClient, TestClient
from sillo.testclient.exceptions import ASGISpecViolation


async def _empty_app(scope, receive, send):
    """An ASGI app that never sends a response."""


async def _debug_app(scope, receive, send):
    await send(
        {
            "type": "http.response.debug",
            "info": {"template": "index.html", "context": {"a": 1}},
        }
    )
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _bad_header_app(header):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": [header]})
        await send({"type": "http.response.body", "body": b"ok"})

    return app


async def _bad_body_type_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": "not-bytes"})


def test_explicit_port_in_url_is_parsed():
    async def app(scope, receive, send):
        assert scope["server"] == ["example.com", 1234]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    client = TestClient(app, base_url="http://example.com:1234")
    response = client.get("/")
    assert response.status_code == 200


def test_missing_host_header_uses_default_port():
    async def app(scope, receive, send):
        headers = dict(scope["headers"])
        assert headers[b"host"] == b"testserver"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    client = TestClient(app)
    request = client.build_request("GET", "/")
    del request.headers["host"]
    response = client.send(request)
    assert response.status_code == 200


def test_missing_host_header_with_non_default_port():
    async def app(scope, receive, send):
        headers = dict(scope["headers"])
        assert headers[b"host"] == b"example.com:1234"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    client = TestClient(app, base_url="http://example.com:1234")
    request = client.build_request("GET", "/")
    del request.headers["host"]
    response = client.send(request)
    assert response.status_code == 200


def test_no_response_raises_asgi_spec_violation():
    client = TestClient(_empty_app)
    with pytest.raises(ASGISpecViolation):
        client.get("/")


def test_no_response_without_conformance_returns_500():
    client = TestClient(
        _empty_app, raise_server_exceptions=False, check_asgi_conformance=False
    )
    response = client.get("/")
    assert response.status_code == 500


def test_debug_message_attaches_template_and_context():
    client = TestClient(_debug_app)
    response = client.get("/")
    assert response.template == "index.html"
    assert response.context == {"a": 1}


@pytest.mark.parametrize(
    "header,match",
    [
        ((123, b"v"), "is not a bytes string"),
        ((b"k\n", b"v"), "contains a newline"),
        ((b"k", 123), "is not a bytes string"),
        ((b"k", b"v\n"), "contains a newline"),
    ],
)
def test_response_header_conformance_violations(header, match):
    client = TestClient(_bad_header_app(header))
    with pytest.raises(ASGISpecViolation, match=match):
        client.get("/")


def test_response_body_conformance_violation():
    client = TestClient(_bad_body_type_app)
    with pytest.raises(ASGISpecViolation, match="body must be a bytes string"):
        client.get("/")


def test_websocket_subprotocols_are_split():
    async def app(scope, receive, send):
        assert scope["subprotocols"] == ["chat", "superchat"]
        message = await receive()
        assert message["type"] == "websocket.connect"
        await send({"type": "websocket.accept"})
        await receive()

    client = TestClient(app)
    with client.websocket_connect("/ws", subprotocols=["chat", "superchat"]) as session:
        session.close()


async def test_async_no_response_raises_asgi_spec_violation():
    client = AsyncTestClient(_empty_app)
    with pytest.raises(ASGISpecViolation):
        await client.get("/")


async def test_async_no_response_without_conformance_returns_500():
    client = AsyncTestClient(
        _empty_app, raise_server_exceptions=False, check_asgi_conformance=False
    )
    response = await client.get("/")
    assert response.status_code == 500


async def test_async_debug_message_attaches_template_and_context():
    client = AsyncTestClient(_debug_app)
    response = await client.get("/")
    assert response.template == "index.html"
    assert response.context == {"a": 1}


async def test_async_response_body_conformance_violation():
    client = AsyncTestClient(_bad_body_type_app)
    with pytest.raises(ASGISpecViolation, match="body must be bytes"):
        await client.get("/")


async def test_async_response_header_conformance_violation():
    client = AsyncTestClient(_bad_header_app((123, b"v")))
    with pytest.raises(ASGISpecViolation, match="headers must be bytes"):
        await client.get("/")


async def test_async_missing_host_header_uses_default_port():
    async def app(scope, receive, send):
        headers = dict(scope["headers"])
        assert headers[b"host"] == b"testserver"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    client = AsyncTestClient(app)
    request = client.build_request("GET", "/")
    del request.headers["host"]
    response = await client.send(request)
    assert response.status_code == 200


async def test_async_explicit_port_and_missing_host_header():
    async def app(scope, receive, send):
        headers = dict(scope["headers"])
        assert headers[b"host"] == b"example.com:1234"
        assert scope["server"] == ["example.com", 1234]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    client = AsyncTestClient(app, base_url="http://example.com:1234")
    request = client.build_request("GET", "/")
    del request.headers["host"]
    response = await client.send(request)
    assert response.status_code == 200
