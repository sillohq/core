from sillo import HttpContext, SilloApp


# Define raw ASGI middleware
def my_asgi_middleware(app):
    async def middleware(scope, receive, send):
        # Example: Log each request path
        print(f"Request path: {scope['path']}")
        await app(scope, receive, send)

    return middleware


def another_asgi_middleware(app):
    async def middleware(scope, receive, send):
        # Example: Add a custom header to each response
        async def custom_send(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((b"x-custom-header", b"custom-value"))
            await send(message)

        await app(scope, receive, custom_send)

    return middleware


# Create SilloApp instance
app = SilloApp()

# Register the raw ASGI middleware factories with use(). Each takes the next
# app and returns an ASGI callable -- a factory whose single ``app`` argument
# the automatic shape detection cannot recognise on its own, so raw=True
# states it explicitly. The last one registered is the outermost layer.
app.use(my_asgi_middleware, raw=True)
app.use(another_asgi_middleware, raw=True)


# Define a simple route
@app.get("/")
async def homepage(ctx: HttpContext):
    return "Hello from sillo!"
