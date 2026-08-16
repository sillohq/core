"""The Sillo application under test.

Written the way Sillo's own documentation writes a handler: typed parameters,
the response builder, no tuning that a normal application would not have. If
this file drifts towards something clever it stops measuring what people
actually deploy.
"""

from __future__ import annotations

from sillo import SilloApp
from sillo.core.http import Request, Response

from sillo_bench.payloads import PLAINTEXT, ROWS_RESPONSE, SMALL_JSON


def create_app() -> SilloApp:
    """Build the Sillo benchmark application.

    Returns:
        A ``SilloApp`` serving every scenario route. ``debug`` is off because
        debug mode renders tracebacks and is not what anyone runs in
        production.
    """
    app = SilloApp(debug=False, title="sillo-bench")

    @app.get("/plaintext")
    async def plaintext(request: Request, response: Response):
        return response.text(PLAINTEXT)

    @app.get("/json")
    async def json_small(request: Request, response: Response):
        return response.json(SMALL_JSON)

    @app.get("/items/{item_id:int}")
    async def item(request: Request, response: Response, item_id: int):
        return response.json({"id": item_id})

    @app.get("/search")
    async def search(request: Request, response: Response):
        params = request.query_params
        return response.json(
            {
                "q": params.get("q", ""),
                "page": int(params.get("page", 1)),
                "per_page": int(params.get("per_page", 20)),
            }
        )

    @app.get("/rows")
    async def rows(request: Request, response: Response):
        return response.json(ROWS_RESPONSE)

    return app


app = create_app()
