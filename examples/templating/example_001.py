from nexios import NexiosApp
from nexios.templating import TemplateConfig, render
from nexios.templating.middleware import template_context

app = NexiosApp()

# Configure templating with custom settings
template_config = TemplateConfig(
    template_dir="templates",  # Directory for templates
    auto_reload=True,  # Auto-reload templates in development
    enable_async=True,  # Enable async rendering
)

# Apply template configuration
app.config.templating = template_config


# Add template context middleware
async def user_context(request: Request) -> dict:
    return {"user": {"name": "Test User", "id": 123}, "app_version": "1.0.0"}


app.add_middleware(
    template_context(
        default_context={"site_name": "Nexios Demo"}, context_processor=user_context
    )
)


@app.get("/")
async def index(request: Request, response: Response) -> Response:
    # Simple template rendering with context
    return await render(
        "index.html",
        {"title": "Welcome to Nexios", "message": "Hello from the template engine!"},
        request=request,
    )


@app.get("/user/{username}")
async def user_profile(request: Request, response: Response, username: str) -> Response:
    # Template rendering with URL parameters
    return await render(
        "user_profile.html",
        {"username": username, "profile_data": {"joined": "2024-01-01", "posts": 42}},
        request=request,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
