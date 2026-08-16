"""The FastAPI application under test.

Idiomatic FastAPI: typed signature parameters so the framework does its own
coercion, and ``PlainTextResponse`` on the plaintext route because returning a
bare string from a default handler would send it as a JSON string and measure
something else.

**The return annotations are load-bearing, and by far the most important line
in this file.** A handler declared ``async def rows() -> dict`` serializes
through pydantic-core's Rust serializer. The same handler with the annotation
removed falls back to FastAPI's pure-Python ``jsonable_encoder``. On the
``rows`` payload that is a **13x** difference — 286µs against 3731µs — which is
larger than any gap between the three frameworks in this suite.

They are kept because showing a framework at its best is the only defensible
choice for a benchmark published by a competitor. Anyone reproducing a FastAPI
number that looks far worse than the one here should check their annotations
first.

The interactive docs and the OpenAPI schema are switched off. They cost nothing
per request, but they add routes, and a benchmark should serve the same route
table everywhere.
"""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import PlainTextResponse

from sillo_bench.payloads import PLAINTEXT, ROWS_RESPONSE, SMALL_JSON


def create_app() -> FastAPI:
    """Build the FastAPI benchmark application.

    Returns:
        A ``FastAPI`` instance serving every scenario route.
    """
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/plaintext", response_class=PlainTextResponse)
    async def plaintext() -> str:
        return PLAINTEXT

    @app.get("/json")
    async def json_small() -> dict:
        return SMALL_JSON

    @app.get("/items/{item_id}")
    async def item(item_id: int) -> dict:
        return {"id": item_id}

    @app.get("/search")
    async def search(
        q: str = Query(default=""),
        page: int = Query(default=1),
        per_page: int = Query(default=20),
    ) -> dict:
        return {"q": q, "page": page, "per_page": per_page}

    @app.get("/rows")
    async def rows() -> dict:
        return ROWS_RESPONSE

    return app


app = create_app()
