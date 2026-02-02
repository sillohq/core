from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.middleware.base import BaseMiddleware


async def logging_middleware(req: Request, res: Response, cnext) -> Response:
    print(f"Request: {req.method} {req.url}")
    response = await cnext()
    print(f"Response: {res.status_code} {response.body}")
    return response


# class based middleware
class LoggingMiddleware(BaseMiddleware):
    async def process_request(self, req: Request, res: Response, cnext) -> Response:
        print(f"Request: {req.method} {req.url}")
        response = await cnext()
        print(f"Response: {res.status_code} {response.body}")
        return response


app = NexiosApp()
app.add_middleware(LoggingMiddleware())
app.add_middleware(logging_middleware)


@app.get("/")
async def index(req: Request, res: Response) -> Response:
    return res.text("Hello, World!")
