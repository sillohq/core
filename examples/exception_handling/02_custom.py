from sillo import silloApp
from sillo.exceptions import HTTPException
from sillo.core.http import Request, Response


class CustomException(HTTPException):
    def __init__(self):
        super().__init__(status_code=400, detail="Custom Exception")


app = silloApp()


@app.get("/test-custom-exception")
async def test_route(req: Request, res: Response) -> Response:
    raise CustomException()


async def handle_custom_exception(
    req: Request, res: Response, exc: CustomException
) -> Response:
    return res.json({"error": str(exc)})


app.add_exception_handler(CustomException, handle_custom_exception)
