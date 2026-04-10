"""
Tests for redirect and streaming responses
"""

from typing import AsyncIterator, Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.testclient import TestClient

# ========== Redirect Response Tests ==========


def test_redirect_response(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test basic redirect response"""
    app = NexiosApp()

    @app.get("/old-path")
    async def old_path(request: Request, response: Response):
        return response.redirect("/new-path")

    @app.get("/new-path")
    async def new_path(request: Request, response: Response):
        return response.text("New location")

    with test_client_factory(app) as client:
        resp = client.get("/old-path", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("location") == "/new-path"


def test_redirect_with_follow(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test redirect with automatic following"""
    app = NexiosApp()

    @app.get("/redirect-me")
    async def redirect_me(request: Request, response: Response):
        return response.redirect("/destination")

    @app.get("/destination")
    async def destination(request: Request, response: Response):
        return response.json({"arrived": True})

    with test_client_factory(app) as client:
        resp = client.get("/redirect-me", follow_redirects=True)
        assert resp.status_code == 200
        assert resp.json()["arrived"] is True


def test_redirect_301_permanent(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test permanent redirect (301)"""
    app = NexiosApp()

    @app.get("/old")
    async def old_endpoint(request: Request, response: Response):
        return response.redirect("/new", status_code=301)

    @app.get("/new")
    async def new_endpoint(request: Request, response: Response):
        return response.text("Moved permanently")

    with test_client_factory(app) as client:
        resp = client.get("/old", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers.get("location") == "/new"


def test_redirect_303_see_other(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test see other redirect (303)"""
    app = NexiosApp()

    @app.post("/submit")
    async def submit_form(request: Request, response: Response):
        return response.redirect("/success", status_code=303)

    @app.get("/success")
    async def success_page(request: Request, response: Response):
        return response.text("Submission successful")

    with test_client_factory(app) as client:
        resp = client.post("/submit", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers.get("location") == "/success"


def test_redirect_307_temporary(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test temporary redirect (307)"""
    app = NexiosApp()

    @app.get("/temp")
    async def temp_redirect(request: Request, response: Response):
        return response.redirect("/target", status_code=307)

    @app.get("/target")
    async def target(request: Request, response: Response):
        return response.text("Temporary target")

    with test_client_factory(app) as client:
        resp = client.get("/temp", follow_redirects=False)
        assert resp.status_code == 307


def test_redirect_308_permanent_redirect(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test permanent redirect (308)"""
    app = NexiosApp()

    @app.get("/old-api")
    async def old_api(request: Request, response: Response):
        return response.redirect("/new-api", status_code=308)

    @app.get("/new-api")
    async def new_api(request: Request, response: Response):
        return response.json({"version": "2.0"})

    with test_client_factory(app) as client:
        resp = client.get("/old-api", follow_redirects=False)
        assert resp.status_code == 308


def test_redirect_external_url(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test redirect to external URL"""
    app = NexiosApp()

    @app.get("/external")
    async def external_redirect(request: Request, response: Response):
        return response.redirect("https://example.com")

    with test_client_factory(app) as client:
        resp = client.get("/external", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers.get("location") == "https://example.com"


def test_redirect_with_query_params(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test redirect preserving query parameters"""
    app = NexiosApp()

    @app.get("/search")
    async def search_redirect(request: Request, response: Response):
        return response.redirect("/results?q=test&page=1")

    @app.get("/results")
    async def results(request: Request, response: Response):
        q = request.query_params.get("q")
        page = request.query_params.get("page")
        return response.json({"query": q, "page": page})

    with test_client_factory(app) as client:
        resp = client.get("/search", follow_redirects=True)
        data = resp.json()
        assert data["query"] == "test"
        assert data["page"] == "1"


def test_redirect_by_route_name(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test redirect using route name instead of URL"""
    app = NexiosApp()

    @app.get("/user/{user_id}", name="user_profile")
    async def get_user(request: Request, response: Response):
        user_id = request.path_params.get("user_id")
        return response.json({"user_id": user_id})

    @app.get("/users")
    async def list_users(request: Request, response: Response):
        return response.redirect(name="user_profile", user_id=42)

    with test_client_factory(app) as client:
        resp = client.get("/users", follow_redirects=False)
        assert resp.status_code == 302
        assert "/user/42" in resp.headers.get("location", "")


def test_redirect_by_route_name_absolute_url(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test redirect by name generates absolute URL"""
    app = NexiosApp()

    @app.get("/profile/{user_id}", name="profile")
    async def profile(request: Request, response: Response):
        return response.json({"id": request.path_params.get("user_id")})

    @app.get("/goto")
    async def goto(request: Request, response: Response):
        return response.redirect(name="profile", user_id=123)

    with test_client_factory(app) as client:
        resp = client.get("/goto", follow_redirects=False)
        location = resp.headers["location"]
        assert location.startswith("http://")
        assert "/profile/123" in location


def test_redirect_name_and_url_error(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test redirect raises error when both url and name provided"""
    app = NexiosApp()

    @app.get("/test")
    async def test_route(request: Request, response: Response):
        return response.redirect(url="/a", name="b")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 500


# ========== Streaming Response Tests ==========


def test_streaming_response(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test basic streaming response"""
    app = NexiosApp()

    async def generate_data():
        for i in range(5):
            yield f"chunk{i}\n"

    @app.get("/stream")
    async def stream_data(request: Request, response: Response):
        return response.stream(generate_data())

    with test_client_factory(app) as client:
        resp = client.get("/stream")
        assert resp.status_code == 200
        content = resp.text
        assert "chunk0" in content
        assert "chunk4" in content


def test_streaming_response_bytes(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test streaming response with bytes"""
    app = NexiosApp()

    async def generate_bytes():
        for i in range(3):
            yield f"data{i}".encode()

    @app.get("/stream-bytes")
    async def stream_bytes(request: Request, response: Response):
        return response.stream(generate_bytes())

    with test_client_factory(app) as client:
        resp = client.get("/stream-bytes")
        assert resp.status_code == 200
        content = resp.content
        assert b"data0" in content
        assert b"data2" in content


def test_streaming_response_with_content_type(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test streaming response with custom content type"""
    app = NexiosApp()

    async def generate_json_lines():
        yield '{"id": 1}\n'
        yield '{"id": 2}\n'
        yield '{"id": 3}\n'

    @app.get("/stream-json")
    async def stream_json(request: Request, response: Response):
        return response.stream(
            generate_json_lines(), content_type="application/x-ndjson"
        )

    with test_client_factory(app) as client:
        resp = client.get("/stream-json")
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "application/x-ndjson" in content_type


def test_streaming_response_with_status_code(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test streaming response with custom status code"""
    app = NexiosApp()

    async def generate_partial():
        yield "partial content"

    @app.get("/stream-partial")
    async def stream_partial(request: Request, response: Response):
        return response.stream(generate_partial(), status_code=206)

    with test_client_factory(app) as client:
        resp = client.get("/stream-partial")
        assert resp.status_code == 206


def test_streaming_large_data(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test streaming large amounts of data"""
    app = NexiosApp()

    async def generate_large_data():
        for i in range(100):
            yield f"line{i}\n"

    @app.get("/stream-large")
    async def stream_large(request: Request, response: Response):
        return response.stream(generate_large_data())

    with test_client_factory(app) as client:
        resp = client.get("/stream-large")
        assert resp.status_code == 200
        lines = resp.text.split("\n")
        # Should have 100 lines plus empty string at end
        assert len([l for l in lines if l]) == 100


def test_streaming_csv_data(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test streaming CSV data"""
    app = NexiosApp()

    async def generate_csv():
        yield "id,name,value\n"
        yield "1,Alice,100\n"
        yield "2,Bob,200\n"
        yield "3,Charlie,300\n"

    @app.get("/stream-csv")
    async def stream_csv(request: Request, response: Response):
        return response.stream(generate_csv(), content_type="text/csv")

    with test_client_factory(app) as client:
        resp = client.get("/stream-csv")
        assert resp.status_code == 200
        content = resp.text
        assert "id,name,value" in content
        assert "Alice" in content
        assert "Charlie" in content


def test_streaming_empty(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test streaming response with no data"""
    app = NexiosApp()

    async def generate_empty():
        return
        yield  # This line is never reached

    @app.get("/stream-empty")
    async def stream_empty(request: Request, response: Response):
        return response.stream(generate_empty())

    with test_client_factory(app) as client:
        resp = client.get("/stream-empty")
        assert resp.status_code == 200


# ========== Combined Tests ==========


def test_redirect_chain(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test multiple redirects in a chain"""
    app = NexiosApp()

    @app.get("/start")
    async def start(request: Request, response: Response):
        return response.redirect("/middle")

    @app.get("/middle")
    async def middle(request: Request, response: Response):
        return response.redirect("/end")

    @app.get("/end")
    async def end(request: Request, response: Response):
        return response.text("Final destination")

    with test_client_factory(app) as client:
        resp = client.get("/start", follow_redirects=True)
        assert resp.status_code == 200
        assert resp.text == "Final destination"


def test_conditional_redirect(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test conditional redirect based on request"""
    app = NexiosApp()

    @app.get("/conditional")
    async def conditional_redirect(request: Request, response: Response):
        redirect_param = request.query_params.get("redirect")
        if redirect_param == "yes":
            return response.redirect("/redirected")
        return response.text("No redirect")

    @app.get("/redirected")
    async def redirected(request: Request, response: Response):
        return response.text("Redirected successfully")

    with test_client_factory(app) as client:
        # Without redirect parameter
        resp1 = client.get("/conditional")
        assert resp1.status_code == 200
        assert resp1.text == "No redirect"

        # With redirect parameter
        resp2 = client.get("/conditional?redirect=yes", follow_redirects=True)
        assert resp2.status_code == 200
        assert resp2.text == "Redirected successfully"
