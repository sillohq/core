"""The Starlette application under test.

Starlette is here because FastAPI is built on it. Comparing the two isolates
what FastAPI's dependency injection, parameter validation and response modelling
cost on top of the ASGI toolkit underneath — which is a more useful number than
either framework's absolute figure, and one only this pairing can produce.

It is also the closest thing in this suite to a floor for a Python ASGI
framework: routing, a request object, a response, and nothing else. Any
framework much slower than Starlette on ``plaintext`` is spending the difference
on machinery of its own.

Starlette does no coercion, so the query scenario casts by hand. That is the
honest representation: the work still happens, it just happens in application
code instead of in the framework.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from sillo_bench.payloads import PLAINTEXT, ROWS_RESPONSE, SMALL_JSON


async def plaintext(request: Request) -> PlainTextResponse:
    """Serve the plaintext scenario."""
    return PlainTextResponse(PLAINTEXT)


async def json_small(request: Request) -> JSONResponse:
    """Serve the small-object scenario."""
    return JSONResponse(SMALL_JSON)


async def item(request: Request) -> JSONResponse:
    """Serve the path-parameter scenario.

    The ``:int`` convertor in the route does the coercion, so this is Starlette's
    equivalent of what the annotated frameworks do from a signature.
    """
    return JSONResponse({"id": request.path_params["item_id"]})


async def search(request: Request) -> JSONResponse:
    """Serve the query-parameter scenario."""
    params = request.query_params
    return JSONResponse(
        {
            "q": params.get("q", ""),
            "page": int(params.get("page", 1)),
            "per_page": int(params.get("per_page", 20)),
        }
    )


async def rows(request: Request) -> JSONResponse:
    """Serve the 200-row scenario."""
    return JSONResponse(ROWS_RESPONSE)


def create_app() -> Starlette:
    """Build the Starlette benchmark application.

    Returns:
        A ``Starlette`` instance serving every scenario route, with debug off.
    """
    return Starlette(
        debug=False,
        routes=[
            Route("/plaintext", plaintext),
            Route("/json", json_small),
            Route("/items/{item_id:int}", item),
            Route("/search", search),
            Route("/rows", rows),
        ],
    )


app = create_app()
