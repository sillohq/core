from pathlib import Path
from typing import TYPE_CHECKING

from sillo import SilloApp
from sillo import html
from sillo.core.http import HttpContext
from sillo.core.routing import Group
from sillo.static import StaticFiles
from sillo.testclient import TestClient

if TYPE_CHECKING:
    from sillo.core.http import HttpContext


def test_static_file_serving():
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir)
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.get("/static/example.txt")
        assert resp.status_code == 200
        assert b"welcome to sillo" in resp.content

        resp = client.get("/static/doesnotexist.txt")
        assert resp.status_code == 404


def test_static_file_types():
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir)
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.get("/static/style.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers.get("content-type", "")
        assert b"body { color: red; }" in resp.content

        resp = client.get("/static/script.js")
        assert resp.status_code == 200
        assert "text/javascript" in resp.headers.get("content-type", "")
        assert b"console.log('Hello from JS');" in resp.content

        resp = client.get("/static/page.html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert b"<img src='image.png' alt='test'>" in resp.content


def test_static_file_subdirectories():
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir)
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.get("/static/subfolder/subfile.txt")
        assert resp.status_code == 200
        assert b"subfolder content" in resp.content

        resp = client.get("/static/nonexistent/subfile.txt")
        assert resp.status_code == 404


def test_static_file_http_methods():
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir)
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.post("/static/example.txt")
        assert resp.status_code == 405

        resp = client.put("/static/example.txt")
        assert resp.status_code == 405

        resp = client.delete("/static/example.txt")
        assert resp.status_code == 405


def test_static_file_cache_headers():
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir)
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.get("/static/example.txt")
        assert resp.status_code == 200
        assert "content-type" in resp.headers


def test_static_file_range_requests():
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir)
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.get("/static/example.txt", headers={"Range": "bytes=0-9"})
        assert resp.status_code == 206
        assert b"welcome to" in resp.content
        assert resp.headers.get("content-range") is not None

        resp = client.get("/static/example.txt", headers={"Range": "bytes=100-200"})
        assert resp.status_code == 206


def test_static_file_error_cases():
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir)
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.get("/static/")
        assert resp.status_code in [200, 404]

        resp = client.get("/static/")
        assert resp.status_code in [200, 404]


def test_static_file_query_params():
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir)
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.get("/static/example.txt?v=1")
        assert resp.status_code == 200
        assert b"welcome to sillo" in resp.content

        resp = client.get("/static/example.txt#section")
        assert resp.status_code == 200
        assert b"welcome to sillo" in resp.content


def test_static_file_allowed_extensions():
    """Test allowed extensions filtering"""
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir, allowed_extensions=["txt", "css"])
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        # These should work
        resp = client.get("/static/example.txt")
        assert resp.status_code == 200

        resp = client.get("/static/style.css")
        assert resp.status_code == 200

        # These should be blocked
        resp = client.get("/static/script.js")
        assert resp.status_code == 404

        resp = client.get("/static/page.html")
        assert resp.status_code == 404


def test_static_file_forbidden_extensions():
    """Test that dangerous extensions are blocked"""
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(
        directory=static_dir, allowed_extensions=["txt", "css", "html"]
    )
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        # Create a forbidden file for testing
        forbidden_file = static_dir / "malicious.php"
        forbidden_file.write_text("<?php echo 'malicious'; ?>")

        try:
            resp = client.get("/static/malicious.php")
            assert resp.status_code == 404  # Should be blocked by extension filter
        finally:
            # Clean up
            if forbidden_file.exists():
                forbidden_file.unlink()


def test_static_file_custom_404_handler():
    """Test custom 404 handler functionality"""

    def custom_404(request: HttpContext) -> Response:
        return html(
            "<html><body><h1>Custom Not Found</h1></body></html>", status_code=404
        )

    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir, custom_404_handler=custom_404)
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.get("/static/nonexistent.txt")
        assert resp.status_code == 404
        assert b"Custom Not Found" in resp.content
        assert "text/html" in resp.headers.get("content-type", "")


def test_static_file_404_handler_that_mutates_response_in_place():
    """A handler that returns None (mutates `response` directly rather than
    returning something new) exercises __call__'s "no handler_result"
    fallback path, which builds the response from `response`
    instead."""

    def custom_404(request: HttpContext) -> None:
        response.status(404)
        response.set_body(b"mutated in place")
        # Deliberately returns None: __call__ falls back to
        # response instead of treating this as the result.

    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir, custom_404_handler=custom_404)
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.get("/static/nonexistent.txt")
        assert resp.status_code == 404
        assert resp.content == b"mutated in place"


def test_static_file_404_handler_returning_a_bare_asgi_callable():
    """A handler returning something directly callable as ASGI (no
    `get_response()`) exercises __call__'s other branch."""

    async def bare_asgi_response(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"bare asgi"})

    def custom_404(request: HttpContext):
        return bare_asgi_response

    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir, custom_404_handler=custom_404)
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.get("/static/nonexistent.txt")
        assert resp.status_code == 404
        assert resp.content == b"bare asgi"


def test_static_file_cache_control():
    """Test cache control headers"""
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(
        directory=static_dir, cache_control="public, max-age=3600"
    )
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        resp = client.get("/static/example.txt")
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "public, max-age=3600"


def test_static_file_multiple_directories():
    """Test serving from multiple directories"""
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_dir2 = Path(__file__).parent.parent / "static" / "subfolder"

    static_files = StaticFiles(directories=[static_dir, static_dir2])
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        # File from first directory
        resp = client.get("/static/example.txt")
        assert resp.status_code == 200
        assert b"welcome to sillo" in resp.content

        # File from second directory (subfolder)
        resp = client.get("/static/subfile.txt")
        assert resp.status_code == 200
        assert b"subfolder content" in resp.content


def test_static_file_extension_case_insensitive():
    """Test that extension filtering is case insensitive"""
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"

    # Create test files with different cases
    (static_dir / "test.TXT").write_text("uppercase extension")
    (static_dir / "test.txt").write_text("lowercase extension")

    try:
        static_files = StaticFiles(directory=static_dir, allowed_extensions=["txt"])
        static_group = Group(path="/static", app=static_files)
        app.add_route(static_group)

        with TestClient(app) as client:
            # Both should work since filtering is case insensitive
            resp = client.get("/static/test.TXT")
            assert resp.status_code == 200

            resp = client.get("/static/test.txt")
            assert resp.status_code == 200

    finally:
        # Clean up test files
        test_files = [static_dir / "test.TXT", static_dir / "test.txt"]
        for test_file in test_files:
            if test_file.exists():
                test_file.unlink()


def test_static_file_empty_extension_list():
    """Test that empty extension list allows all files"""
    app = SilloApp()
    static_dir = Path(__file__).parent.parent / "static"
    static_files = StaticFiles(directory=static_dir, allowed_extensions=[])
    static_group = Group(path="/static", app=static_files)
    app.add_route(static_group)

    with TestClient(app) as client:
        # All files should be served when no restrictions
        resp = client.get("/static/example.txt")
        assert resp.status_code == 200

        resp = client.get("/static/style.css")
        assert resp.status_code == 200

        resp = client.get("/static/script.js")
        assert resp.status_code == 200
