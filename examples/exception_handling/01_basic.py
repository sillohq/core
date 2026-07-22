from sillo import silloApp
from sillo.exceptions import HTTPException
from sillo.core.http import Request, Response

app = silloApp()


@app.route("/error")
async def error_handler(req: Request, res: Response) -> Response:
    raise HTTPException(status_code=400, detail="error occurred")


@app.add_exception_handler(HTTPException)
async def http_error_handler(
    req: Request, res: Response, exc: HTTPException
) -> Response:
    return await res.json({"error": exc.detail}, status_code=exc.status_code)


# app.add_exception_handler(ValueError, handle_value_error)
# app.add_exception_handler(404, handle_not_found)
