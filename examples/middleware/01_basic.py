from sillo import HttpContext, SilloApp
from sillo.middleware import BaseMiddleware


async def logging_middleware(ctx: HttpContext, call_next):
    print(f"Request: {ctx.method} {ctx.url}")
    response = await call_next()
    print(f"Response: {response.status_code}")
    return response


# class based middleware
class LoggingMiddleware(BaseMiddleware):
    async def dispatch(self, ctx: HttpContext, call_next):
        print(f"Request: {ctx.method} {ctx.url}")
        response = await call_next()
        print(f"Response: {response.status_code}")
        return response


app = SilloApp()
app.use(LoggingMiddleware())
app.use(logging_middleware)


@app.get("/")
async def index(ctx: HttpContext):
    return "Hello, World!"
