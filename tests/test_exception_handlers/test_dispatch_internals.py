"""The dispatch helper, the bodyless statuses, and validation flattening.

Three parts of ``sillo.exception_handler`` that the integration tests reach
around rather than through: ``wrap_http_exceptions`` is called directly by
callers that drive the pipeline themselves, the 204/304 branch of
``http_exception`` exists because those statuses may not carry a body, and
``pydantic_validation_error_handler`` reshapes an error list whose interesting
cases are the nested ones.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from sillo.core.http import HttpContext
from sillo.exception_handler import (
    ExceptionMiddleware,
    pydantic_validation_error_handler,
    wrap_http_exceptions,
)
from sillo.exceptions import HTTPException


def make_ctx() -> HttpContext:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    return HttpContext(scope, None)


class TestWrapHttpExceptions:
    """The standalone dispatcher: run the chain, and route what it raises."""

    async def test_a_successful_call_is_returned_untouched(self):
        request = make_ctx()
        sentinel = object()

        async def call_next():
            return sentinel

        result = await wrap_http_exceptions(
            request, call_next, {}, {})

        assert result is sentinel

    async def test_a_status_handler_claims_a_matching_http_exception(self):
        request = make_ctx()
        seen: dict = {}

        async def call_next():
            raise HTTPException(status_code=418, detail="teapot")

        async def on_418(req, exc):
            seen["exc"] = exc
            return "handled-by-status"

        result = await wrap_http_exceptions(
            request, call_next, {}, {418: on_418}
        )

        assert result == "handled-by-status"
        assert seen["exc"].status_code == 418

    async def test_an_http_exception_with_no_status_handler_falls_to_the_class(self):
        """Status handlers are consulted first, but a miss must not stop the
        search -- otherwise registering a handler for one status code
        silently disables class-based handling for every other."""
        request = make_ctx()

        async def call_next():
            raise HTTPException(status_code=404, detail="nope")

        async def on_class(req, exc):
            return "handled-by-class"

        result = await wrap_http_exceptions(
            request,
            call_next,
            {HTTPException: on_class},
            {418: lambda *a: None},
        )

        assert result == "handled-by-class"

    async def test_a_class_handler_claims_an_ordinary_exception(self):
        request = make_ctx()

        class Boom(Exception):
            pass

        async def call_next():
            raise Boom("bang")

        async def on_boom(req, exc):
            return f"handled {exc}"

        result = await wrap_http_exceptions(
            request, call_next, {Boom: on_boom}, {}
        )

        assert result == "handled bang"

    async def test_a_base_class_handler_catches_a_subclass(self):
        """Lookup walks the MRO, which is what makes a handler registered for
        a base class cover everything beneath it."""
        request = make_ctx()

        class Base(Exception):
            pass

        class Derived(Base):
            pass

        async def call_next():
            raise Derived("derived")

        async def on_base(req, exc):
            return "handled-by-base"

        result = await wrap_http_exceptions(
            request, call_next, {Base: on_base}, {}
        )

        assert result == "handled-by-base"

    async def test_an_unhandled_exception_is_re_raised(self):
        """Re-raised rather than swallowed: this is how it reaches
        ServerErrorMiddleware and becomes a 500 instead of a None response."""
        request = make_ctx()

        class Unhandled(Exception):
            pass

        async def call_next():
            raise Unhandled("nobody wants this")

        with pytest.raises(Unhandled, match="nobody wants this"):
            await wrap_http_exceptions(
            request, call_next, {}, {})

    async def test_the_unhandled_traceback_is_logged(self, caplog):
        """The re-raise is the behaviour; the log is what makes it
        diagnosable, since the exception may be reshaped further up."""
        request = make_ctx()

        async def call_next():
            raise RuntimeError("for the log")

        with pytest.raises(RuntimeError), caplog.at_level("ERROR", logger="sillo"):
            await wrap_http_exceptions(
            request, call_next, {}, {})

        assert "for the log" in caplog.text

    @pytest.mark.parametrize(
        ("handlers", "statuses"),
        [(None, None), ({}, None), (None, {})],
    )
    async def test_absent_registries_default_to_empty(self, handlers, statuses):
        """Both arguments are defaulted rather than assumed. They used to be
        assigned to themselves inside a `try/except KeyError`, which could not
        raise and so defaulted nothing."""
        request = make_ctx()

        async def call_next():
            return "fine"

        assert (
            await wrap_http_exceptions(
            request, call_next, handlers, statuses)
            == "fine"
        )


class TestStatusesThatMayNotCarryABody:
    """204 and 304 are prohibited from having one, so the handler must not
    serialize the detail into them."""

    @pytest.mark.parametrize("status", [204, 304])
    async def test_the_response_is_empty(self, status):
        request = make_ctx()
        middleware = ExceptionMiddleware()

        result = await middleware.http_exception(
            request, HTTPException(status_code=status, detail="ignored")
        )

        built = result
        assert built.status_code == status
        assert built.body == b""

    @pytest.mark.parametrize("status", [204, 304])
    async def test_the_exception_headers_still_reach_the_response(self, status):
        request = make_ctx()
        middleware = ExceptionMiddleware()

        result = await middleware.http_exception(
            request,
            HTTPException(
                status_code=status, detail="ignored", headers={"x-marker": "kept"}
            ),
        )

        keys = [k.decode("latin-1") for k, _ in result.raw_headers]
        assert "x-marker" in keys

    async def test_an_ordinary_status_still_carries_its_detail(self):
        request = make_ctx()
        middleware = ExceptionMiddleware()

        result = await middleware.http_exception(
            request, HTTPException(status_code=400, detail="bad input")
        )

        built = result
        assert built.status_code == 400
        assert b"bad input" in built.body


class TestValidationErrorFlattening:
    """A pydantic error list becomes a dict the client can index by field."""

    def _error(self, model, payload) -> ValidationError:
        try:
            model(**payload)
        except ValidationError as caught:
            return caught
        raise AssertionError("the payload was valid")

    async def test_a_top_level_field_maps_directly(self):
        class User(BaseModel):
            name: str

        request = make_ctx()
        exc = self._error(User, {})

        result = await pydantic_validation_error_handler(
            request, exc)
        body = result.body.decode()

        assert '"name"' in body
        assert "Validation Error" in body

    async def test_a_two_level_field_nests(self):
        class Address(BaseModel):
            city: str

        class User(BaseModel):
            address: Address

        request = make_ctx()
        exc = self._error(User, {"address": {}})

        result = await pydantic_validation_error_handler(
            request, exc)
        body = result.body.decode()

        # {"address": {"city": ...}} rather than a flattened "address.city".
        assert '"address"' in body
        assert '"city"' in body
        assert "address.city" not in body

    async def test_a_deeper_path_is_flattened_with_dots(self):
        class Street(BaseModel):
            number: int

        class Address(BaseModel):
            street: Street

        class User(BaseModel):
            address: Address

        request = make_ctx()
        exc = self._error(User, {"address": {"street": {}}})

        result = await pydantic_validation_error_handler(
            request, exc)
        body = result.body.decode()

        assert "address.street.number" in body

    async def test_a_nested_field_does_not_overwrite_a_scalar_message(self):
        """The subtle branch: a one-level error writes a *string* under a key,
        and a two-level error then needs a dict under that same key. Writing
        into the string would raise; replacing it silently is the deliberate
        choice, and it has to be exercised or the guard is untested.
        """
        request = make_ctx()

        class Anything(BaseModel):
            field: str

        exc = self._error(Anything, {})
        # Rebuild the loc structure by hand: pydantic will not naturally
        # produce both shapes for one key in a single validation pass.
        original = exc.errors

        def both_shapes():
            return [
                {"loc": ("conflict",), "msg": "scalar first"},
                {"loc": ("conflict", "inner"), "msg": "then nested"},
            ]

        exc.errors = both_shapes  # type: ignore[method-assign]
        try:
            result = await pydantic_validation_error_handler(
            request, exc)
        finally:
            exc.errors = original  # type: ignore[method-assign]

        body = result.body.decode()
        assert '"inner"' in body
        assert "then nested" in body

    async def test_the_status_is_422(self):
        class User(BaseModel):
            name: str

        request = make_ctx()
        exc = self._error(User, {})

        result = await pydantic_validation_error_handler(
            request, exc)

        assert result.status_code == 422


class TestTheMiddlewareGuards:
    """``ExceptionMiddleware`` is built before it has an inner application --
    the registries outlive any one chain -- so it has to say so if it is ever
    called without one being assigned."""

    async def test_serving_without_an_inner_app_explains_itself(self):
        middleware = ExceptionMiddleware()
        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}

        with pytest.raises(RuntimeError, match="without an inner"):
            await middleware(scope, None, None)

    async def test_a_non_http_scope_passes_straight_through(self):
        """Nothing here can answer a websocket or lifespan message, so the
        cheapest correct thing is to get out of the way."""
        seen: dict = {}

        async def inner(scope, receive, send):
            seen["scope"] = scope

        middleware = ExceptionMiddleware(inner)
        scope = {"type": "lifespan"}

        await middleware(scope, None, None)

        assert seen["scope"] is scope

    async def test_an_http_scope_with_no_handlers_passes_straight_through(self):
        """With both registries empty there is no exception this could answer,
        so the request goes to the inner app with no `try` around it."""
        seen: dict = {}

        async def inner(scope, receive, send):
            seen["ran"] = True

        middleware = ExceptionMiddleware(inner)
        middleware._exception_handlers = {}
        middleware._status_handlers = {}
        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}

        await middleware(scope, None, None)

        assert seen["ran"] is True


class TestTheRequestAndResponseValidationHandlers:
    async def test_a_request_validation_error_lists_what_failed(self):
        from sillo.exception_handler import request_validation_error_handler
        from sillo.validation import RequestValidationError

        request = make_ctx()
        exc = RequestValidationError([{"loc": ("body", "name"), "msg": "required"}])

        result = await request_validation_error_handler(request, exc)
        built = result

        assert built.status_code == 422
        assert b"required" in built.body

    async def test_a_response_validation_error_is_a_500_and_says_nothing_useful(self):
        """The client caused none of this and can act on none of it, so the
        body is generic. The detail goes to the log instead."""
        from sillo.exception_handler import response_validation_error_handler
        from sillo.validation import ResponseValidationError

        request = make_ctx()
        exc = ResponseValidationError([{"loc": ("response",), "msg": "wrong shape"}])

        result = await response_validation_error_handler(request, exc)
        built = result

        assert built.status_code == 500
        assert b"wrong shape" not in built.body
        assert b"Internal Server Error" in built.body

    async def test_the_response_validation_detail_is_logged(self, caplog):
        from sillo.exception_handler import response_validation_error_handler
        from sillo.validation import ResponseValidationError

        request = make_ctx()
        exc = ResponseValidationError([{"loc": ("response",), "msg": "wrong shape"}])

        with caplog.at_level("ERROR", logger="sillo"):
            await response_validation_error_handler(request, exc)

        assert "Response validation failed" in caplog.text
