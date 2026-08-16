"""The Litestar application under test.

Litestar is the closest comparison Sillo has: a batteries-included async
framework with typed handlers, coercion from annotations, and its own
serializer. Where FastAPI answers "what does validation cost", Litestar answers
"what does a modern competitor achieve while offering the same things".

Its serializer is `msgspec <https://github.com/jcrist/msgspec>`_ rather than
pure Python, which is worth watching on the ``rows`` scenario specifically —
that row is largely a serializer benchmark and Litestar, FastAPI and Sillo take
three genuinely different approaches to it.

``sync_to_thread=False`` is set on nothing here because every handler is already
``async``; the flag exists for sync handlers and would not apply.
"""

from __future__ import annotations

from litestar import Litestar, MediaType, get

from sillo_bench.payloads import PLAINTEXT, ROWS_RESPONSE, SMALL_JSON


@get("/plaintext", media_type=MediaType.TEXT)
async def plaintext() -> str:
    """Serve the plaintext scenario.

    ``media_type`` is explicit because the default would encode the string as
    JSON, which would measure the serializer on a scenario meant to isolate
    request overhead.
    """
    return PLAINTEXT


@get("/json")
async def json_small() -> dict:
    """Serve the small-object scenario."""
    return SMALL_JSON


@get("/items/{item_id:int}")
async def item(item_id: int) -> dict:
    """Serve the path-parameter scenario.

    Args:
        item_id: Coerced from the path by Litestar, from the annotation.
    """
    return {"id": item_id}


@get("/search")
async def search(q: str = "", page: int = 1, per_page: int = 20) -> dict:
    """Serve the query-parameter scenario.

    Args:
        q: The search term.
        page: Page number, coerced by Litestar.
        per_page: Page size, coerced by Litestar.
    """
    return {"q": q, "page": page, "per_page": per_page}


@get("/rows")
async def rows() -> dict:
    """Serve the 200-row scenario."""
    return ROWS_RESPONSE


def create_app() -> Litestar:
    """Build the Litestar benchmark application.

    Returns:
        A ``Litestar`` instance serving every scenario route. OpenAPI is left
        at its default, which registers documentation routes but costs nothing
        per request on the paths measured here.
    """
    return Litestar(
        route_handlers=[plaintext, json_small, item, search, rows],
        debug=False,
    )


app = create_app()
