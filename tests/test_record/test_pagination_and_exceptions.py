"""``sillo.record`` pagination handlers and database exception handlers.

The handlers turn ORM failures into HTTP responses, which is the code that runs
when a request has already gone wrong — so a bug here replaces a real error
with a confusing one. The pagination handlers are the adapters between a
Tortoise queryset and the generic paginator.
"""

import inspect

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import (
    DoesNotExist,
    IntegrityError,
    OperationalError,
    ValidationError,
)

from sillo import SilloApp
from sillo.core.http import Request, Response
from sillo.record import Model
from sillo.record.exceptions import (
    handle_does_not_exist,
    handle_integrity_error,
    handle_operational_error,
    handle_validation_error,
    register_db_exception_handlers,
)
from sillo.record.pagination import SyncTortoiseDataHandler, TortoiseDataHandler
from sillo.testclient import TestClient

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class Widget(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)

    class Meta:
        table = "pagination_widgets"


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["tests.test_record.test_pagination_and_exceptions"]},
    )
    if _has_global_fallback:
        init_kwargs["_enable_global_fallback"] = True
    await Tortoise.init(**init_kwargs)
    await Tortoise.generate_schemas()
    yield
    try:
        await Tortoise._drop_databases()
    except Exception:
        pass
    try:
        await Tortoise.close_connections()
    except Exception:
        pass


def _request():
    return Request(
        {
            "type": "http", "method": "GET", "path": "/", "raw_path": b"/",
            "query_string": b"", "headers": [(b"host", b"test")],
            "client": ("127.0.0.1", 1), "server": ("t", 80),
            "scheme": "http", "http_version": "1.1", "root_path": "",
        }
    )


class TestAsyncPaginationHandler:
    async def test_total_items_counts_the_queryset(self):
        for i in range(5):
            await Widget.create(name=f"w{i}")

        handler = TortoiseDataHandler(Widget.all())

        assert await handler.get_total_items() == 5

    async def test_get_items_applies_offset_and_limit(self):
        for i in range(5):
            await Widget.create(name=f"w{i}")

        handler = TortoiseDataHandler(Widget.all())
        page = await handler.get_items(offset=1, limit=2)

        assert len(page) == 2

    async def test_an_empty_queryset_has_no_items(self):
        handler = TortoiseDataHandler(Widget.all())

        assert await handler.get_total_items() == 0
        assert await handler.get_items(offset=0, limit=10) == []


class TestSyncPaginationHandler:
    def test_total_items_counts_the_list(self):
        handler = SyncTortoiseDataHandler([1, 2, 3])

        assert handler.get_total_items() == 3

    def test_get_items_slices_the_list(self):
        handler = SyncTortoiseDataHandler([1, 2, 3, 4, 5])

        assert handler.get_items(offset=1, limit=2) == [2, 3]

    def test_an_offset_past_the_end_gives_nothing(self):
        handler = SyncTortoiseDataHandler([1, 2])

        assert handler.get_items(offset=10, limit=5) == []

    def test_an_empty_list_has_no_items(self):
        handler = SyncTortoiseDataHandler([])

        assert handler.get_total_items() == 0
        assert handler.get_items(offset=0, limit=10) == []


class TestExceptionHandlers:
    async def test_a_missing_row_becomes_404(self):
        response = Response(request=_request())

        result = await handle_does_not_exist(
            _request(), response, DoesNotExist("Widget matching query does not exist")
        )

        assert result.get_response().status_code == 404

    async def test_an_integrity_error_becomes_409(self):
        response = Response(request=_request())

        result = await handle_integrity_error(
            _request(), response, IntegrityError("UNIQUE constraint failed")
        )

        assert result.get_response().status_code == 409

    async def test_a_validation_error_becomes_422(self):
        response = Response(request=_request())

        result = await handle_validation_error(
            _request(), response, ValidationError("name is too long")
        )

        assert result.get_response().status_code == 422

    async def test_an_operational_error_becomes_503(self):
        # Service Unavailable rather than a bare 500: an operational error is
        # the database being unreachable, which is a transient condition a
        # client may retry.
        response = Response(request=_request())

        result = await handle_operational_error(
            _request(), response, OperationalError("no such table")
        )

        assert result.get_response().status_code == 503


class TestHandlerRegistration:
    def test_every_handler_is_registered_on_the_app(self):
        app = SilloApp(debug=False)

        register_db_exception_handlers(app)

        registered = app.exceptions_handler._exception_handlers
        for exc_type in (
            DoesNotExist,
            IntegrityError,
            ValidationError,
            OperationalError,
        ):
            assert exc_type in registered

    def test_a_missing_row_is_a_404_end_to_end(self):
        app = SilloApp(debug=False)
        register_db_exception_handlers(app)

        @app.get("/widget")
        async def get_widget(request: Request, response: Response):
            raise DoesNotExist("Widget matching query does not exist")

        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.get("/widget").status_code == 404

    def test_a_duplicate_is_a_409_end_to_end(self):
        app = SilloApp(debug=False)
        register_db_exception_handlers(app)

        @app.post("/widget")
        async def create_widget(request: Request, response: Response):
            raise IntegrityError("UNIQUE constraint failed: widgets.name")

        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.post("/widget").status_code == 409
