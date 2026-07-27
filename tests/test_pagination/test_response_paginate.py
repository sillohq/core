"""
``response.paginate()`` and ``response.apaginate()``.

The paginator strategies themselves are covered elsewhere; what is tested here
is the response-level shortcut — that it picks the right strategy by name,
reads the page from the live request's query string, and separates strategy
configuration from per-call parameter overrides.
"""

from typing import Callable

import pytest

from sillo import silloApp
from sillo.core.http import Request, Response
from sillo.pagination import LimitOffsetPagination, PageNumberPagination
from sillo.testclient import TestClient

ITEMS = [{"id": i, "name": f"item-{i:03d}"} for i in range(50)]


def _app(handler_body, *, route="/items"):
    app = silloApp()
    app.get(route)(handler_body)
    return app


# ── the synchronous shortcut ─────────────────────────────────────────────


@pytest.fixture
def sync_app():
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate(ITEMS)

    return app


def test_the_first_page_is_returned(
    sync_app, test_client_factory: Callable[[silloApp], TestClient]
):
    with test_client_factory(sync_app) as client:
        body = client.get("/items").json()
    assert body["items"][0]["id"] == 0


def test_the_page_is_bounded(
    sync_app, test_client_factory: Callable[[silloApp], TestClient]
):
    with test_client_factory(sync_app) as client:
        body = client.get("/items").json()
    assert len(body["items"]) == 20


def test_the_metadata_reports_the_total(
    sync_app, test_client_factory: Callable[[silloApp], TestClient]
):
    with test_client_factory(sync_app) as client:
        body = client.get("/items").json()
    assert body["pagination"]["total_items"] == 50


def test_the_page_comes_from_the_query_string(
    sync_app, test_client_factory: Callable[[silloApp], TestClient]
):
    with test_client_factory(sync_app) as client:
        body = client.get("/items?page=2").json()
    assert body["items"][0]["id"] == 20
    assert body["pagination"]["page"] == 2


def test_the_page_size_comes_from_the_query_string(
    sync_app, test_client_factory: Callable[[silloApp], TestClient]
):
    with test_client_factory(sync_app) as client:
        body = client.get("/items?page_size=5").json()
    assert len(body["items"]) == 5


def test_the_last_page_may_be_short(
    sync_app, test_client_factory: Callable[[silloApp], TestClient]
):
    with test_client_factory(sync_app) as client:
        body = client.get("/items?page=3").json()
    assert len(body["items"]) == 10


def test_an_empty_collection_paginates(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate([])

    with test_client_factory(app) as client:
        body = client.get("/items").json()
    assert body["items"] == []
    assert body["pagination"]["total_items"] == 0


# ── strategy selection ───────────────────────────────────────────────────


def test_limit_offset_by_name(test_client_factory: Callable[[silloApp], TestClient]):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate(ITEMS, strategy="limit_offset")

    with test_client_factory(app) as client:
        body = client.get("/items?limit=5&offset=10").json()
    assert len(body["items"]) == 5
    assert body["items"][0]["id"] == 10


def test_cursor_by_name(test_client_factory: Callable[[silloApp], TestClient]):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate(ITEMS, strategy="cursor", sort_field="id")

    with test_client_factory(app) as client:
        response = client.get("/items")
    assert response.status_code == 200
    assert response.json()["items"]


def test_an_unknown_strategy_name_is_rejected(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate(ITEMS, strategy="telepathy")

    with test_client_factory(app, raise_server_exceptions=False) as client:
        assert client.get("/items").status_code == 500


def test_a_strategy_instance_is_used_as_given(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate(ITEMS, strategy=PageNumberPagination(default_page_size=3))

    with test_client_factory(app) as client:
        assert len(client.get("/items").json()["items"]) == 3


def test_an_instance_of_another_strategy(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate(ITEMS, strategy=LimitOffsetPagination(default_limit=4))

    with test_client_factory(app) as client:
        assert len(client.get("/items").json()["items"]) == 4


# ── configuration versus overrides ───────────────────────────────────────


def test_strategy_configuration_is_applied(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Recognised keys configure the strategy rather than being forwarded to
    ``paginate`` as parameter overrides."""
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate(ITEMS, default_page_size=7)

    with test_client_factory(app) as client:
        assert len(client.get("/items").json()["items"]) == 7


def test_a_custom_page_parameter_name(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate(ITEMS, page_param="p")

    with test_client_factory(app) as client:
        body = client.get("/items?p=2").json()
    assert body["items"][0]["id"] == 20


def test_the_max_page_size_caps_the_request(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """A client asking for everything in one page must not be able to."""
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate(ITEMS, max_page_size=10)

    with test_client_factory(app) as client:
        assert len(client.get("/items?page_size=1000").json()["items"]) == 10


def test_an_unrecognised_keyword_is_a_parameter_override(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate(ITEMS, page=3)

    with test_client_factory(app) as client:
        assert client.get("/items").json()["pagination"]["page"] == 3


def test_an_override_beats_the_query_string(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return response.paginate(ITEMS, page=1)

    with test_client_factory(app) as client:
        assert client.get("/items?page=2").json()["pagination"]["page"] == 1


# ── the asynchronous shortcut ────────────────────────────────────────────


@pytest.fixture
def async_app():
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return await response.apaginate(ITEMS)

    return app


def test_the_async_form_paginates(
    async_app, test_client_factory: Callable[[silloApp], TestClient]
):
    with test_client_factory(async_app) as client:
        body = client.get("/items").json()
    assert len(body["items"]) == 20
    assert body["pagination"]["total_items"] == 50


def test_the_async_form_reads_the_query_string(
    async_app, test_client_factory: Callable[[silloApp], TestClient]
):
    with test_client_factory(async_app) as client:
        assert client.get("/items?page=2").json()["items"][0]["id"] == 20


def test_the_async_form_supports_limit_offset(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return await response.apaginate(ITEMS, strategy="limit_offset")

    with test_client_factory(app) as client:
        body = client.get("/items?limit=3&offset=6").json()
    assert len(body["items"]) == 3
    assert body["items"][0]["id"] == 6


def test_the_async_form_supports_cursor(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return await response.apaginate(ITEMS, strategy="cursor", sort_field="id")

    with test_client_factory(app) as client:
        assert client.get("/items").status_code == 200


def test_the_async_form_rejects_an_unknown_strategy(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return await response.apaginate(ITEMS, strategy="telepathy")

    with test_client_factory(app, raise_server_exceptions=False) as client:
        assert client.get("/items").status_code == 500


def test_the_async_form_takes_a_strategy_instance(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return await response.apaginate(
            ITEMS, strategy=PageNumberPagination(default_page_size=6)
        )

    with test_client_factory(app) as client:
        assert len(client.get("/items").json()["items"]) == 6


def test_the_async_form_applies_configuration(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return await response.apaginate(ITEMS, default_page_size=8)

    with test_client_factory(app) as client:
        assert len(client.get("/items").json()["items"]) == 8


def test_the_async_form_paginates_an_empty_collection(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp()

    @app.get("/items")
    async def items(request: Request, response: Response):
        return await response.apaginate([])

    with test_client_factory(app) as client:
        assert client.get("/items").json()["items"] == []


def test_both_forms_agree(
    sync_app, async_app, test_client_factory: Callable[[silloApp], TestClient]
):
    with test_client_factory(sync_app) as client:
        sync_body = client.get("/items?page=2").json()
    with test_client_factory(async_app) as client:
        async_body = client.get("/items?page=2").json()
    assert sync_body["items"] == async_body["items"]
