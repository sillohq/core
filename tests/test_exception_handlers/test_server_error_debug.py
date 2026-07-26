"""
The debug error page.

``ServerErrorMiddleware`` renders an unhandled exception as an HTML traceback
in debug mode and as a terse response otherwise. Almost none of the rendering
was exercised, which matters because this code runs precisely when the
application is already failing — a bug here hides the original error.
"""

import pytest

from sillo import silloApp
from sillo.core.error.handler import ServerErrorMiddleware
from sillo.testclient import TestClient


@pytest.fixture
def middleware():
    return ServerErrorMiddleware(debug=True)


@pytest.fixture
def caught():
    """A real raised exception, so it carries a traceback."""
    try:
        raise ValueError("something went wrong")
    except ValueError as exc:
        return exc


# ── HTML rendering ───────────────────────────────────────────────────────


def test_html_includes_the_exception_type(middleware, caught):
    assert "ValueError" in middleware.generate_html(caught)


def test_html_includes_the_message(middleware, caught):
    assert "something went wrong" in middleware.generate_html(caught)


def test_html_is_a_document(middleware, caught):
    html = middleware.generate_html(caught)
    assert "<html" in html.lower()
    assert "</html>" in html.lower()


def test_html_names_the_file_the_error_came_from(middleware, caught):
    assert "test_server_error_debug" in middleware.generate_html(caught)


def test_html_respects_the_frame_limit(middleware):
    def recurse(n):
        if n == 0:
            raise RuntimeError("bottom")
        recurse(n - 1)

    try:
        recurse(12)
    except RuntimeError as exc:
        short = middleware.generate_html(exc, limit=2)
        long = middleware.generate_html(exc, limit=10)
    assert len(long) > len(short)


def test_html_for_an_exception_with_no_traceback(middleware):
    """A never-raised exception has no frames and must still render."""
    assert "ValueError" in middleware.generate_html(ValueError("bare"))


# ── plain text rendering ─────────────────────────────────────────────────


def test_plain_text_includes_the_exception(middleware, caught):
    text = middleware.generate_plain_text(caught)
    assert "ValueError" in text
    assert "something went wrong" in text


def test_plain_text_is_not_html(middleware, caught):
    assert "<html" not in middleware.generate_plain_text(caught).lower()


# ── JSON rendering ───────────────────────────────────────────────────────


def test_error_json_is_valid_json(middleware, caught):
    import json

    payload = json.loads(middleware._generate_error_json(caught, "ValueError"))
    assert isinstance(payload, dict)


def test_error_json_names_the_exception(middleware, caught):
    assert "ValueError" in middleware._generate_error_json(caught, "ValueError")


# ── fragment helpers ─────────────────────────────────────────────────────


def test_format_line_marks_the_failing_line(middleware):
    """The line the error occurred on must be visually distinguishable."""
    current = middleware.format_line(0, "x = 1", 10, 10)
    other = middleware.format_line(0, "x = 1", 10, 11)
    assert current != other


def test_format_locals_renders_values(middleware):
    out = middleware._format_locals({"count": 42, "name": "ada"})
    assert "count" in out and "42" in out


def test_format_locals_with_nothing_to_show(middleware):
    assert isinstance(middleware._format_locals({}), str)


def test_format_locals_survives_an_unreprable_value(middleware):
    class Hostile:
        def __repr__(self):
            raise RuntimeError("no repr for you")

    assert isinstance(middleware._format_locals({"bad": Hostile()}), str)


def test_system_info_reports_the_python_version(middleware):
    import sys

    assert sys.version.split()[0] in middleware._format_system_info()


def test_debugging_suggestions_are_produced(middleware, caught):
    assert isinstance(
        middleware._generate_debugging_suggestions(caught, "ValueError"), str
    )


@pytest.mark.parametrize(
    "exc,name",
    [
        (KeyError("k"), "KeyError"),
        (AttributeError("a"), "AttributeError"),
        (TypeError("t"), "TypeError"),
        (ImportError("i"), "ImportError"),
        (ZeroDivisionError("z"), "ZeroDivisionError"),
    ],
)
def test_suggestions_cover_common_exception_types(middleware, exc, name):
    """Each branch of the suggestion lookup should render without error."""
    assert isinstance(middleware._generate_debugging_suggestions(exc, name), str)


# ── end to end ───────────────────────────────────────────────────────────


def test_debug_mode_returns_an_html_traceback():
    app = silloApp(debug=True)

    @app.get("/boom")
    async def boom(request, response):
        raise ValueError("kaboom")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")

    assert resp.status_code == 500
    assert "kaboom" in resp.text


def test_non_debug_mode_hides_the_detail():
    app = silloApp(debug=False)

    @app.get("/boom")
    async def boom(request, response):
        raise ValueError("secret internal detail")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")

    assert resp.status_code == 500
    assert "secret internal detail" not in resp.text


def test_a_custom_server_error_handler_takes_over():
    async def custom(request, response, exc):
        return response.json({"handled": str(exc)}, status_code=500)

    app = silloApp(debug=False, server_error_handler=custom)

    @app.get("/boom")
    async def boom(request, response):
        raise ValueError("kaboom")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")

    assert resp.status_code == 500
    assert resp.json()["handled"] == "kaboom"
