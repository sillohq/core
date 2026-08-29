"""
The 404 handler.

Format follows the client's ``Accept`` header; detail follows the
application's ``debug`` flag. The defect these guard against was a
``try: settings = None`` block that made the debug branch unreachable, so
every 404 in every deployment answered as though debug were on.
"""

import pytest

from sillo import SilloApp
from sillo import text
from sillo.handlers.not_found import GENERIC_MESSAGE
from sillo.testclient import TestClient

BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
API = {"Accept": "application/json"}
PLAIN = {"Accept": "text/plain"}


@pytest.fixture
def production():
    return TestClient(SilloApp(debug=False))


@pytest.fixture
def development():
    return TestClient(SilloApp(debug=True))


# ── content negotiation ──────────────────────────────────────────────────


def test_a_browser_gets_the_html_page(production):
    response = production.get("/missing", headers=BROWSER)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "<!DOCTYPE html>" in response.text


def test_an_api_client_gets_json(production):
    response = production.get("/missing", headers=API)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["status"] == 404
    assert response.json()["error"] == "Not Found"


def test_json_is_the_default_when_no_preference_is_expressed(production):
    response = production.get("/missing")

    assert response.headers["content-type"].startswith("application/json")


def test_a_wildcard_accept_is_not_treated_as_a_request_for_html(production):
    """``*/*`` comes from curl and HTTP clients, not from browsers."""
    response = production.get("/missing", headers={"Accept": "*/*"})

    assert response.headers["content-type"].startswith("application/json")


def test_a_client_wanting_neither_gets_plain_text(production):
    response = production.get("/missing", headers=PLAIN)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.startswith("404 - Not Found")


# ── debug gating ─────────────────────────────────────────────────────────


def test_production_returns_the_generic_message(production):
    """The regression: this used to leak the exception detail regardless."""
    assert production.get("/missing", headers=API).json()["message"] == GENERIC_MESSAGE


def test_production_never_includes_a_traceback(production):
    assert "traceback" not in production.get("/missing", headers=API).json()


def test_production_keeps_the_generic_message_in_html(production):
    assert GENERIC_MESSAGE in production.get("/missing", headers=BROWSER).text


def test_debug_returns_the_exception_detail(development):
    message = development.get("/missing", headers=API).json()["message"]

    assert message != GENERIC_MESSAGE


def test_debug_includes_a_traceback(development):
    assert "traceback" in development.get("/missing", headers=API).json()


def test_the_flag_is_read_from_the_application_not_assumed():
    """Both settings are honoured; neither is hard-coded."""
    on = TestClient(SilloApp(debug=True)).get("/missing", headers=API).json()["message"]
    off = TestClient(SilloApp(debug=False)).get("/missing", headers=API).json()["message"]

    assert on != off
    assert off == GENERIC_MESSAGE


def test_debug_is_off_when_there_is_no_application_to_ask():
    """A bare scope should say less, not more."""
    from sillo.core.http import HttpContext
    from sillo.handlers.not_found import _debug_enabled

    scope = {"type": "http", "method": "GET", "path": "/x", "headers": []}
    assert _debug_enabled(HttpContext(scope, None)) is False


# ── the handler only applies to misses ───────────────────────────────────


def test_a_matched_route_is_untouched(production):
    app = SilloApp(debug=False)

    @app.get("/exists")
    async def handler(request):
        return text("here")

    assert TestClient(app).get("/exists").status_code == 200
