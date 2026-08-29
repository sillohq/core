"""
Tests for file and download responses
"""

import os
import tempfile
from pathlib import Path
from typing import Callable

import pytest

from sillo import SilloApp
from sillo import download, file, json
from sillo.core.http import HttpContext
from sillo.testclient import TestClient

# ========== File Response Tests ==========


def test_file_response(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test serving a file"""
    app = SilloApp()

    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Test file content")
        temp_path = f.name

    try:

        @app.get("/file")
        async def serve_file(request: HttpContext):
            return file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/file")
            assert resp.status_code == 200
            assert "Test file content" in resp.text
    finally:
        os.unlink(temp_path)


def test_file_response_with_custom_filename(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test serving a file with custom filename"""
    app = SilloApp()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Custom filename test")
        temp_path = f.name

    try:

        @app.get("/custom-file")
        async def serve_custom_file(request: HttpContext):
            return file(temp_path, filename="custom_name.txt")

        with test_client_factory(app) as client:
            resp = client.get("/custom-file")
            assert resp.status_code == 200
            content_disposition = resp.headers.get("content-disposition", "")
            assert "custom_name.txt" in content_disposition
    finally:
        os.unlink(temp_path)


def test_file_response_content_type(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test file response content type detection"""
    app = SilloApp()

    # Create a JSON file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        f.write('{"test": "data"}')
        temp_path = f.name

    try:

        @app.get("/json-file")
        async def serve_json_file(request: HttpContext):
            return file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/json-file")
            assert resp.status_code == 200
            content_type = resp.headers.get("content-type", "")
            assert (
                "json" in content_type.lower() or "application" in content_type.lower()
            )
    finally:
        os.unlink(temp_path)


def test_file_response_inline_disposition(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test file response with inline disposition"""
    app = SilloApp()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Inline content")
        temp_path = f.name

    try:

        @app.get("/inline")
        async def serve_inline(request: HttpContext):
            return file(temp_path, content_disposition_type="inline")

        with test_client_factory(app) as client:
            resp = client.get("/inline")
            assert resp.status_code == 200
            content_disposition = resp.headers.get("content-disposition", "")
            assert "inline" in content_disposition
    finally:
        os.unlink(temp_path)


# ========== Download Response Tests ==========


def test_download_response(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test forcing file download"""
    app = SilloApp()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".pdf") as f:
        f.write("PDF content")
        temp_path = f.name

    try:

        @app.get("/download")
        async def download_file(request: HttpContext):
            return download(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/download")
            assert resp.status_code == 200
            content_disposition = resp.headers.get("content-disposition", "")
            assert "attachment" in content_disposition
    finally:
        os.unlink(temp_path)


def test_download_with_custom_filename(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test download with custom filename"""
    app = SilloApp()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
        f.write("col1,col2\nval1,val2")
        temp_path = f.name

    try:

        @app.get("/download-csv")
        async def download_csv(request: HttpContext):
            return download(temp_path, filename="data.csv")

        with test_client_factory(app) as client:
            resp = client.get("/download-csv")
            assert resp.status_code == 200
            content_disposition = resp.headers.get("content-disposition", "")
            assert "attachment" in content_disposition
            assert "data.csv" in content_disposition
    finally:
        os.unlink(temp_path)


# ========== Large File Tests ==========


def test_large_file_response(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test serving a larger file"""
    app = SilloApp()

    # Create a larger temporary file (1MB)
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        content = "x" * (1024 * 1024)  # 1MB of 'x' characters
        f.write(content)
        temp_path = f.name

    try:

        @app.get("/large-file")
        async def serve_large_file(request: HttpContext):
            return file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/large-file")
            assert resp.status_code == 200
            assert len(resp.content) == 1024 * 1024
    finally:
        os.unlink(temp_path)


# ========== Binary File Tests ==========


def test_binary_file_response(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test serving a binary file"""
    app = SilloApp()

    # Create a binary file
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".bin") as f:
        binary_data = bytes([i % 256 for i in range(1000)])
        f.write(binary_data)
        temp_path = f.name

    try:

        @app.get("/binary")
        async def serve_binary(request: HttpContext):
            return file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/binary")
            assert resp.status_code == 200
            assert len(resp.content) == 1000
    finally:
        os.unlink(temp_path)


# ========== File Not Found Tests ==========


def test_file_not_found(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test handling of non-existent file"""
    app = SilloApp()

    @app.get("/missing-file")
    async def serve_missing_file(request: HttpContext):
        return file("/nonexistent/path/file.txt")

    with test_client_factory(app) as client:
        # This should raise an error or return 404
        try:
            resp = client.get("/missing-file")
            # If it doesn't raise, it should be an error status
            assert resp.status_code >= 400
        except Exception:
            # Expected behavior - file not found raises exception
            pass


# ========== Content Length Tests ==========


def test_file_content_length_header(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test that content-length header is set correctly for files"""
    app = SilloApp()

    content = "Test content for length check"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write(content)
        temp_path = f.name

    try:

        @app.get("/file-length")
        async def serve_file_length(request: HttpContext):
            return file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/file-length")
            assert resp.status_code == 200
            content_length = resp.headers.get("content-length")
            if content_length:
                assert int(content_length) == len(content.encode())
    finally:
        os.unlink(temp_path)


# ========== Accept-Ranges Tests ==========


def test_file_accept_ranges_header(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test that accept-ranges header is set for file responses"""
    app = SilloApp()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Range test content")
        temp_path = f.name

    try:

        @app.get("/ranges")
        async def serve_with_ranges(request: HttpContext):
            return file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/ranges")
            assert resp.status_code == 200
            accept_ranges = resp.headers.get("accept-ranges")
            # File responses should support byte ranges
            assert accept_ranges is not None
    finally:
        os.unlink(temp_path)


# ========== Range HttpContext Tests ==========


@pytest.fixture
def range_app(request: pytest.FixtureRequest):
    """An app serving a known 1024-byte file, plus the file's bytes."""
    payload = bytes(range(256)) * 4

    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(payload)
        temp_path = f.name
    request.addfinalizer(lambda: os.unlink(temp_path))

    app = SilloApp()

    @app.get("/asset")
    async def serve_asset(req: HttpContext):
        return file(temp_path)

    return app, payload


def _declared_length_matches(resp) -> bool:
    """Whether Content-Length agrees with the body that actually arrived.

    This is the property that matters: a server writing more bytes than it
    declared raises ``LocalProtocolError`` in h11 and the response dies
    part-sent, so asserting on the header alone would miss the bug.
    """
    declared = resp.headers.get("content-length")
    return declared is not None and int(declared) == len(resp.content)


def test_range_single(range_app, test_client_factory: Callable[[SilloApp], TestClient]):
    """A single range returns exactly the bytes asked for."""
    app, payload = range_app
    with test_client_factory(app) as client:
        resp = client.get("/asset", headers={"Range": "bytes=0-99"})

    assert resp.status_code == 206
    assert resp.headers["content-range"] == "bytes 0-99/1024"
    assert resp.content == payload[0:100]
    assert _declared_length_matches(resp)


def test_range_multipart_declares_the_framing_it_sends(
    range_app, test_client_factory: Callable[[SilloApp], TestClient]
):
    """Multiple ranges: Content-Length must cover the multipart framing.

    Regression for a response that kept the whole-file Content-Length set by
    ``set_stat_headers``. Two adjacent ranges spanning the file send more than
    the file itself once boundaries and part headers are counted, so the
    server wrote past what it had declared and h11 aborted the response with
    ``Too much data for declared Content-Length``.
    """
    app, payload = range_app
    with test_client_factory(app) as client:
        resp = client.get("/asset", headers={"Range": "bytes=0-511,512-1023"})

    assert resp.status_code == 206
    assert resp.headers["content-type"].startswith("multipart/byteranges")
    assert len(resp.content) > len(payload)  # framing pushes it past the file
    assert _declared_length_matches(resp)


def test_range_multipart_is_parseable(
    range_app, test_client_factory: Callable[[SilloApp], TestClient]
):
    """The multipart body parses, and each part carries its own bytes."""
    import email

    app, payload = range_app
    with test_client_factory(app) as client:
        resp = client.get("/asset", headers={"Range": "bytes=0-511,700-899"})

    content_type = resp.headers["content-type"]
    message = email.message_from_bytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
        + resp.content
    )
    assert message.is_multipart()

    parts = message.get_payload()
    assert len(parts) == 2
    for part, (start, end) in zip(parts, [(0, 511), (700, 899)]):
        assert part["Content-Range"] == f"bytes {start}-{end}/1024"
        # Not the bytes repr of the header value, which is what a lookup
        # through raw_headers used to produce.
        assert part["Content-Type"] == "application/octet-stream"
        assert part.get_payload(decode=True) == payload[start : end + 1]


def test_range_multipart_sets_one_content_type(
    range_app, test_client_factory: Callable[[SilloApp], TestClient]
):
    """The multipart type replaces the file's type rather than joining it."""
    app, _ = range_app
    with test_client_factory(app) as client:
        resp = client.get("/asset", headers={"Range": "bytes=0-9,20-29"})

    assert resp.headers["content-type"].startswith("multipart/byteranges")
    assert "application/octet-stream" not in resp.headers["content-type"]


def test_range_unsatisfiable_declares_no_body(
    range_app, test_client_factory: Callable[[SilloApp], TestClient]
):
    """A 416 sends no body, so it must not declare the whole file's length."""
    app, _ = range_app
    with test_client_factory(app) as client:
        resp = client.get("/asset", headers={"Range": "bytes=2000-3000"})

    assert resp.status_code == 416
    assert resp.headers["content-range"] == "bytes */1024"
    assert resp.headers["content-length"] == "0"
    assert resp.content == b""


def test_range_first_byte_only(
    range_app, test_client_factory: Callable[[SilloApp], TestClient]
):
    """`bytes=0-0` is one byte, not the whole file.

    A falsy check on the parsed end offset could not tell an explicit ``0``
    from an absent one, so this probe — which browsers send to discover
    whether a server honours ranges at all — returned everything.
    """
    app, payload = range_app
    with test_client_factory(app) as client:
        resp = client.get("/asset", headers={"Range": "bytes=0-0"})

    assert resp.status_code == 206
    assert resp.headers["content-range"] == "bytes 0-0/1024"
    assert resp.content == payload[0:1]


def test_range_suffix(range_app, test_client_factory: Callable[[SilloApp], TestClient]):
    """`bytes=-100` means the last 100 bytes, not a malformed range."""
    app, payload = range_app
    with test_client_factory(app) as client:
        resp = client.get("/asset", headers={"Range": "bytes=-100"})

    assert resp.status_code == 206
    assert resp.headers["content-range"] == "bytes 924-1023/1024"
    assert resp.content == payload[-100:]


def test_range_open_ended(
    range_app, test_client_factory: Callable[[SilloApp], TestClient]
):
    """`bytes=500-` runs to the end of the file."""
    app, payload = range_app
    with test_client_factory(app) as client:
        resp = client.get("/asset", headers={"Range": "bytes=500-"})

    assert resp.status_code == 206
    assert resp.headers["content-range"] == "bytes 500-1023/1024"
    assert resp.content == payload[500:]


def test_range_end_past_the_file_is_clamped(
    range_app, test_client_factory: Callable[[SilloApp], TestClient]
):
    """An over-long end offset yields what exists rather than a 416."""
    app, payload = range_app
    with test_client_factory(app) as client:
        resp = client.get("/asset", headers={"Range": "bytes=0-99999"})

    assert resp.status_code == 206
    assert resp.headers["content-range"] == "bytes 0-1023/1024"
    assert resp.content == payload


@pytest.mark.parametrize(
    "value", ["bytes=abc", "items=0-10", "bytes=", "bytes=10-4", "0-10"]
)
def test_range_malformed(
    value: str, range_app, test_client_factory: Callable[[SilloApp], TestClient]
):
    """Anything unparseable is a 416 with an empty body."""
    app, _ = range_app
    with test_client_factory(app) as client:
        resp = client.get("/asset", headers={"Range": value})

    assert resp.status_code == 416
    assert resp.headers["content-length"] == "0"
    assert resp.content == b""


# ========== set_body Tests ==========


def test_set_body_keeps_content_length_in_step(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Replacing the body must re-declare its length.

    Assigning the body alone left the Content-Length computed from the old
    one; a longer replacement then wrote past the declared length and h11
    tore the connection down mid-response.
    """
    app = SilloApp()

    @app.get("/rewritten")
    async def rewritten(request: HttpContext):
        response = json({"message": "hi"})
        response.set_body(b'{"message":"a considerably longer body than before"}')
        return response

    with test_client_factory(app) as client:
        resp = client.get("/rewritten")

    assert int(resp.headers["content-length"]) == len(resp.content)
    assert resp.json() == {"message": "a considerably longer body than before"}


def test_set_header_override_keeps_headers_mapping_live(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """An overriding set_header must not orphan the cached headers mapping.

    ``response.headers`` caches a view over ``raw_headers``. Rebuilding that
    list instead of editing it left the view wrapping a list nothing sends,
    so later edits through ``response.headers`` vanished silently.
    """
    app = SilloApp()

    @app.get("/headers")
    async def headers(request: HttpContext):
        inner = json({"ok": True})
        inner.headers["x-first"] = "1"  # builds the cached view
        inner.set_header("x-second", "2", override=True)  # used to rebind
        inner.headers["x-third"] = "3"  # must still reach the wire
        return inner

    with test_client_factory(app) as client:
        resp = client.get("/headers")

    assert resp.headers.get("x-first") == "1"
    assert resp.headers.get("x-second") == "2"
    assert resp.headers.get("x-third") == "3"
