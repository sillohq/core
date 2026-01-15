from pathlib import Path
from typing import TYPE_CHECKING

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.static import StaticFiles
from nexios.testclient import TestClient

if TYPE_CHECKING:
    from nexios.http import Request, Response


def test_static_file_serving():
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(StaticFiles(directory=static_dir), "/static")

    with TestClient(app) as client:
        resp = client.get("/static/example.txt")
        assert resp.status_code == 200
        assert b"welcome to nexios" in resp.content

        resp = client.get("/static/doesnotexist.txt")
        assert resp.status_code == 404


def test_static_file_types():
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(StaticFiles(directory=static_dir), "/static")

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
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(StaticFiles(directory=static_dir), "/static")

    with TestClient(app) as client:
        resp = client.get("/static/subfolder/subfile.txt")
        assert resp.status_code == 200
        assert b"subfolder content" in resp.content

        resp = client.get("/static/nonexistent/subfile.txt")
        assert resp.status_code == 404


def test_static_file_http_methods():
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(StaticFiles(directory=static_dir), "/static")

    with TestClient(app) as client:
        resp = client.post("/static/example.txt")
        assert resp.status_code == 405

        resp = client.put("/static/example.txt")
        assert resp.status_code == 405

        resp = client.delete("/static/example.txt")
        assert resp.status_code == 405


def test_static_file_cache_headers():
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(StaticFiles(directory=static_dir), "/static")

    with TestClient(app) as client:
        resp = client.get("/static/example.txt")
        assert resp.status_code == 200
        assert "content-type" in resp.headers


def test_static_file_range_requests():
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(StaticFiles(directory=static_dir), "/static")

    with TestClient(app) as client:
        resp = client.get("/static/example.txt", headers={"Range": "bytes=0-9"})
        assert resp.status_code == 206
        assert b"welcome to" in resp.content
        assert resp.headers.get("content-range") is not None

        resp = client.get("/static/example.txt", headers={"Range": "bytes=100-200"})
        assert resp.status_code == 206


def test_static_file_error_cases():
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(StaticFiles(directory=static_dir), "/static")

    with TestClient(app) as client:
        resp = client.get("/static/")
        assert resp.status_code in [200, 404]

        resp = client.get("/static/")
        assert resp.status_code in [200, 404]


def test_static_file_query_params():
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(StaticFiles(directory=static_dir), "/static")

    with TestClient(app) as client:
        resp = client.get("/static/example.txt?v=1")
        assert resp.status_code == 200
        assert b"welcome to nexios" in resp.content

        resp = client.get("/static/example.txt#section")
        assert resp.status_code == 200
        assert b"welcome to nexios" in resp.content


def test_static_file_allowed_extensions():
    """Test allowed extensions filtering"""
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(
        StaticFiles(directory=static_dir, allowed_extensions=["txt", "css"]), "/static"
    )

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
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(
        StaticFiles(directory=static_dir, allowed_extensions=["txt", "css", "html"]),
        "/static",
    )

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

    def custom_404(request: Request, response: Response) -> Response:
        return response.html(
            "<html><body><h1>Custom Not Found</h1></body></html>", status_code=404
        )

    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(
        StaticFiles(directory=static_dir, custom_404_handler=custom_404), "/static"
    )

    with TestClient(app) as client:
        resp = client.get("/static/nonexistent.txt")
        assert resp.status_code == 404
        assert b"Custom Not Found" in resp.content
        assert "text/html" in resp.headers.get("content-type", "")


def test_static_file_cache_control():
    """Test cache control headers"""
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(
        StaticFiles(directory=static_dir, cache_control="public, max-age=3600"),
        "/static",
    )

    with TestClient(app) as client:
        resp = client.get("/static/example.txt")
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "public, max-age=3600"


def test_static_file_multiple_directories():
    """Test serving from multiple directories"""
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    static_dir2 = Path(__file__).parent / "static" / "subfolder"

    app.register(StaticFiles(directories=[static_dir, static_dir2]), "/static")

    with TestClient(app) as client:
        # File from first directory
        resp = client.get("/static/example.txt")
        assert resp.status_code == 200
        assert b"welcome to nexios" in resp.content

        # File from second directory (subfolder)
        resp = client.get("/static/subfile.txt")
        assert resp.status_code == 200
        assert b"subfolder content" in resp.content


def test_static_file_extension_case_insensitive():
    """Test that extension filtering is case insensitive"""
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"

    # Create test files with different cases
    (static_dir / "test.TXT").write_text("uppercase extension")
    (static_dir / "test.txt").write_text("lowercase extension")

    try:
        app.register(
            StaticFiles(directory=static_dir, allowed_extensions=["txt"]), "/static"
        )

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
    app = NexiosApp()
    static_dir = Path(__file__).parent / "static"
    app.register(StaticFiles(directory=static_dir, allowed_extensions=[]), "/static")

    with TestClient(app) as client:
        # All files should be served when no restrictions
        resp = client.get("/static/example.txt")
        assert resp.status_code == 200

        resp = client.get("/static/style.css")
        assert resp.status_code == 200

        resp = client.get("/static/script.js")
        assert resp.status_code == 200
