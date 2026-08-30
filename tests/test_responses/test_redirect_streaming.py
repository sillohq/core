"""
Tests for redirect and streaming responses
"""

from typing import AsyncIterator, Callable

import pytest

from sillo import SilloApp
from sillo import json, redirect, stream, text
from sillo.core.http import HttpContext
from sillo.testclient import TestClient

# ========== Redirect Response Tests ==========


def test_redirect_response(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test basic redirect response"""
    app = SilloApp()

    @app.get("/old-path")
    async def old_path(ctx: HttpContext):
        return redirect("/new-path")

    @app.get("/new-path")
    async def new_path(ctx: HttpContext):
        return text("New location")

    with test_client_factory(app) as client:
        resp = client.get("/old-path", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("location") == "/new-path"


def test_redirect_with_follow(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test redirect with automatic following"""
    app = SilloApp()

    @app.get("/redirect-me")
    async def redirect_me(ctx: HttpContext):
        return redirect("/destination")

    @app.get("/destination")
    async def destination(ctx: HttpContext):
        return json({"arrived": True})

    with test_client_factory(app) as client:
        resp = client.get("/redirect-me", follow_redirects=True)
        assert resp.status_code == 200
        assert resp.json()["arrived"] is True


def test_redirect_301_permanent(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test permanent redirect (301)"""
    app = SilloApp()

    @app.get("/old")
    async def old_endpoint(ctx: HttpContext):
        return redirect("/new", status_code=301)

    @app.get("/new")
    async def new_endpoint(ctx: HttpContext):
        return text("Moved permanently")

    with test_client_factory(app) as client:
        resp = client.get("/old", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers.get("location") == "/new"


def test_redirect_303_see_other(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test see other redirect (303)"""
    app = SilloApp()

    @app.post("/submit")
    async def submit_form(ctx: HttpContext):
        return redirect("/success", status_code=303)

    @app.get("/success")
    async def success_page(ctx: HttpContext):
        return text("Submission successful")

    with test_client_factory(app) as client:
        resp = client.post("/submit", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers.get("location") == "/success"


def test_redirect_307_temporary(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test temporary redirect (307)"""
    app = SilloApp()

    @app.get("/temp")
    async def temp_redirect(ctx: HttpContext):
        return redirect("/target", status_code=307)

    @app.get("/target")
    async def target(ctx: HttpContext):
        return text("Temporary target")

    with test_client_factory(app) as client:
        resp = client.get("/temp", follow_redirects=False)
        assert resp.status_code == 307


def test_redirect_308_permanent_redirect(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test permanent redirect (308)"""
    app = SilloApp()

    @app.get("/old-api")
    async def old_api(ctx: HttpContext):
        return redirect("/new-api", status_code=308)

    @app.get("/new-api")
    async def new_api(ctx: HttpContext):
        return json({"version": "2.0"})

    with test_client_factory(app) as client:
        resp = client.get("/old-api", follow_redirects=False)
        assert resp.status_code == 308


def test_redirect_external_url(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test redirect to external URL"""
    app = SilloApp()

    @app.get("/external")
    async def external_redirect(ctx: HttpContext):
        return redirect("https://example.com")

    with test_client_factory(app) as client:
        resp = client.get("/external", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("location") == "https://example.com"


def test_redirect_with_query_params(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test redirect preserving query parameters"""
    app = SilloApp()

    @app.get("/search")
    async def search_redirect(ctx: HttpContext):
        return redirect("/results?q=test&page=1")

    @app.get("/results")
    async def results(ctx: HttpContext):
        q = ctx.query_params.get("q")
        page = ctx.query_params.get("page")
        return json({"query": q, "page": page})

    with test_client_factory(app) as client:
        resp = client.get("/search", follow_redirects=True)
        data = resp.json()
        assert data["query"] == "test"
        assert data["page"] == "1"


def test_redirect_by_route_name(test_client_factory: Callable[[SilloApp], TestClient]):
    """A named route is resolved with ctx.url_for and handed to redirect()."""
    app = SilloApp()

    @app.get("/user/{user_id}", name="user_profile")
    async def get_user(ctx: HttpContext):
        user_id = ctx.path_params.get("user_id")
        return json({"user_id": user_id})

    @app.get("/users")
    async def list_users(ctx: HttpContext):
        return redirect(ctx.url_for("user_profile", user_id=42))

    with test_client_factory(app) as client:
        resp = client.get("/users", follow_redirects=False)
        assert resp.status_code == 302
        assert "/user/42" in resp.headers.get("location", "")


def test_redirect_by_route_name_resolves_the_path(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """ctx.url_for resolves the name to a path, which redirect() sends as-is."""
    app = SilloApp()

    @app.get("/profile/{user_id}", name="profile")
    async def profile(ctx: HttpContext):
        return json({"id": ctx.path_params.get("user_id")})

    @app.get("/goto")
    async def goto(ctx: HttpContext):
        return redirect(ctx.url_for("profile", user_id=123))

    with test_client_factory(app) as client:
        resp = client.get("/goto", follow_redirects=False)
        assert resp.headers["location"] == "/profile/123"


def test_redirect_to_an_unknown_route_name_is_an_error(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """url_for raises for a name no route claims, rather than redirecting nowhere."""
    app = SilloApp()

    @app.get("/test")
    async def test_route(ctx: HttpContext):
        return redirect(ctx.url_for("no-such-route"))

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 500


# ========== Streaming Response Tests ==========


def test_streaming_response(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test basic streaming response"""
    app = SilloApp()

    async def generate_data():
        for i in range(5):
            yield f"chunk{i}\n"

    @app.get("/stream")
    async def stream_data(ctx: HttpContext):
        return stream(generate_data())

    with test_client_factory(app) as client:
        resp = client.get("/stream")
        assert resp.status_code == 200
        content = resp.text
        assert "chunk0" in content
        assert "chunk4" in content


def test_streaming_response_bytes(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test streaming response with bytes"""
    app = SilloApp()

    async def generate_bytes():
        for i in range(3):
            yield f"data{i}".encode()

    @app.get("/stream-bytes")
    async def stream_bytes(ctx: HttpContext):
        return stream(generate_bytes())

    with test_client_factory(app) as client:
        resp = client.get("/stream-bytes")
        assert resp.status_code == 200
        content = resp.content
        assert b"data0" in content
        assert b"data2" in content


def test_streaming_response_with_content_type(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test streaming response with custom content type"""
    app = SilloApp()

    async def generate_json_lines():
        yield '{"id": 1}\n'
        yield '{"id": 2}\n'
        yield '{"id": 3}\n'

    @app.get("/stream-json")
    async def stream_json(ctx: HttpContext):
        return stream(
            generate_json_lines(), content_type="application/x-ndjson"
        )

    with test_client_factory(app) as client:
        resp = client.get("/stream-json")
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "application/x-ndjson" in content_type


def test_streaming_response_with_status_code(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test streaming response with custom status code"""
    app = SilloApp()

    async def generate_partial():
        yield "partial content"

    @app.get("/stream-partial")
    async def stream_partial(ctx: HttpContext):
        return stream(generate_partial(), status_code=206)

    with test_client_factory(app) as client:
        resp = client.get("/stream-partial")
        assert resp.status_code == 206


def test_streaming_large_data(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test streaming large amounts of data"""
    app = SilloApp()

    async def generate_large_data():
        for i in range(100):
            yield f"line{i}\n"

    @app.get("/stream-large")
    async def stream_large(ctx: HttpContext):
        return stream(generate_large_data())

    with test_client_factory(app) as client:
        resp = client.get("/stream-large")
        assert resp.status_code == 200
        lines = resp.text.split("\n")
        # Should have 100 lines plus empty string at end
        assert len([l for l in lines if l]) == 100


def test_streaming_csv_data(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test streaming CSV data"""
    app = SilloApp()

    async def generate_csv():
        yield "id,name,value\n"
        yield "1,Alice,100\n"
        yield "2,Bob,200\n"
        yield "3,Charlie,300\n"

    @app.get("/stream-csv")
    async def stream_csv(ctx: HttpContext):
        return stream(generate_csv(), content_type="text/csv")

    with test_client_factory(app) as client:
        resp = client.get("/stream-csv")
        assert resp.status_code == 200
        content = resp.text
        assert "id,name,value" in content
        assert "Alice" in content
        assert "Charlie" in content


def test_streaming_empty(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test streaming response with no data"""
    app = SilloApp()

    async def generate_empty():
        return
        yield  # This line is never reached

    @app.get("/stream-empty")
    async def stream_empty(ctx: HttpContext):
        return stream(generate_empty())

    with test_client_factory(app) as client:
        resp = client.get("/stream-empty")
        assert resp.status_code == 200


# ========== Combined Tests ==========


def test_redirect_chain(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test multiple redirects in a chain"""
    app = SilloApp()

    @app.get("/start")
    async def start(ctx: HttpContext):
        return redirect("/middle")

    @app.get("/middle")
    async def middle(ctx: HttpContext):
        return redirect("/end")

    @app.get("/end")
    async def end(ctx: HttpContext):
        return text("Final destination")

    with test_client_factory(app) as client:
        resp = client.get("/start", follow_redirects=True)
        assert resp.status_code == 200
        assert resp.text == "Final destination"


def test_conditional_redirect(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test conditional redirect based on request"""
    app = SilloApp()

    @app.get("/conditional")
    async def conditional_redirect(ctx: HttpContext):
        redirect_param = ctx.query_params.get("redirect")
        if redirect_param == "yes":
            return redirect("/redirected")
        return text("No redirect")

    @app.get("/redirected")
    async def redirected(ctx: HttpContext):
        return text("Redirected successfully")

    with test_client_factory(app) as client:
        # Without redirect parameter
        resp1 = client.get("/conditional")
        assert resp1.status_code == 200
        assert resp1.text == "No redirect"

        # With redirect parameter
        resp2 = client.get("/conditional?redirect=yes", follow_redirects=True)
        assert resp2.status_code == 200
        assert resp2.text == "Redirected successfully"
