from sillo.http import Request, Response
from sillo.routing import Router
from sillo.templating import render

index_router = Router()


@index_router.get("/")
async def index(request: Request, response: Response):
    """Index route for the application."""
    return await render("index.html")
