from nexios import NexiosApp


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


# Create NexiosApp instance
app = NexiosApp()

# Wrap ASGI middleware using Nexios' wrap_middleware
app.wrap_asgi(my_asgi_middleware)
app.wrap_asgi(another_asgi_middleware)


# Define a simple route
@app.route("/")
async def homepage(req: Request, res: Response) -> Response:
    return res.text("Hello from Nexios!")
