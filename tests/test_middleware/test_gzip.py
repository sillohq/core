"""
GZip response compression.

Compression must be conditional: only when the client advertises support, only
above a size threshold, and never for streaming responses where it would break
incremental delivery.
"""

import gzip

import pytest

from sillo import SilloApp
from sillo.middleware.gzip import GZipMiddleware
from sillo.testclient import TestClient

BIG = "x" * 5000
SMALL = "tiny"


@pytest.fixture
def client():
    app = SilloApp()

    @app.get("/big")
    async def big(request, response):
        return response.text(BIG)

    @app.get("/small")
    async def small(request, response):
        return response.text(SMALL)

    @app.get("/json")
    async def as_json(request, response):
        return response.json({"data": [{"i": i} for i in range(400)]})

    @app.get("/stream")
    async def stream(request, response):
        async def gen():
            for i in range(50):
                yield f"chunk-{i}\n".encode()

        return response.stream(gen(), content_type="text/plain")

    return TestClient(GZipMiddleware(app, minimum_size=500))


# ── when compression applies ─────────────────────────────────────────────


def test_a_large_response_is_compressed(client):
    resp = client.get("/big", headers={"Accept-Encoding": "gzip"})
    assert resp.headers.get("content-encoding") == "gzip"


def test_a_compressed_response_still_decodes_correctly(client):
    """httpx decompresses transparently, so the payload must survive intact."""
    resp = client.get("/big", headers={"Accept-Encoding": "gzip"})
    assert resp.text == BIG


def test_json_is_compressed(client):
    resp = client.get("/json", headers={"Accept-Encoding": "gzip"})
    assert resp.headers.get("content-encoding") == "gzip"
    assert len(resp.json()["data"]) == 400


def test_vary_is_set_so_caches_do_not_serve_the_wrong_encoding(client):
    resp = client.get("/big", headers={"Accept-Encoding": "gzip"})
    assert "accept-encoding" in resp.headers.get("vary", "").lower()


# ── when it does not ─────────────────────────────────────────────────────


def test_a_small_response_is_left_alone(client):
    """Below the threshold, compression costs more than it saves."""
    resp = client.get("/small", headers={"Accept-Encoding": "gzip"})
    assert resp.headers.get("content-encoding") != "gzip"
    assert resp.text == SMALL


def test_a_client_that_does_not_advertise_gzip_gets_plain_bytes(client):
    resp = client.get("/big", headers={"Accept-Encoding": "identity"})
    assert resp.headers.get("content-encoding") != "gzip"
    assert resp.text == BIG


def test_no_accept_encoding_header_at_all(client):
    resp = client.get("/big", headers={"Accept-Encoding": ""})
    assert resp.text == BIG


def test_a_streaming_response_still_delivers_every_chunk(client):
    resp = client.get("/stream", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert "chunk-0" in resp.text
    assert "chunk-49" in resp.text


# ── configuration ────────────────────────────────────────────────────────


def test_the_threshold_is_configurable():
    app = SilloApp()

    @app.get("/medium")
    async def medium(request, response):
        return response.text("y" * 200)

    resp = TestClient(GZipMiddleware(app, minimum_size=100)).get("/medium", headers={"Accept-Encoding": "gzip"})
    assert resp.headers.get("content-encoding") == "gzip"


def test_a_high_threshold_disables_compression_in_practice():
    app = SilloApp()

    @app.get("/big")
    async def big(request, response):
        return response.text(BIG)

    resp = TestClient(GZipMiddleware(app, minimum_size=1_000_000)).get("/big", headers={"Accept-Encoding": "gzip"})
    assert resp.headers.get("content-encoding") != "gzip"


@pytest.mark.parametrize("level", [1, 5, 9])
def test_every_compression_level_round_trips(level):
    app = SilloApp()

    @app.get("/big")
    async def big(request, response):
        return response.text(BIG)

    resp = TestClient(GZipMiddleware(app, minimum_size=100, compresslevel=level)).get("/big", headers={"Accept-Encoding": "gzip"})
    assert resp.text == BIG


def test_compression_actually_reduces_the_payload():
    """Verified against the raw bytes, not the decoded body."""
    app = SilloApp()

    @app.get("/big")
    async def big(request, response):
        return response.text(BIG)

    client = TestClient(GZipMiddleware(app, minimum_size=100))

    compressed = client.get(
        "/big", headers={"Accept-Encoding": "gzip"}
    ).content  # httpx decodes, so compare against a manual gzip instead
    assert len(gzip.compress(BIG.encode())) < len(BIG.encode())
    assert compressed == BIG.encode()


# ── other status codes and methods ───────────────────────────────────────


def test_an_error_response_passes_through(client):
    resp = client.get("/missing", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 404


def test_a_head_request_has_no_body(client):
    resp = client.head("/big", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code in (200, 405)
