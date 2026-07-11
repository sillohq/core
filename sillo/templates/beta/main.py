from config import app_config
from routes.index import index

from sillo import silloApp
from sillo.routing import Route

# Create the application
app = silloApp(title="{{project_name_title}}")


@app.on_startup
async def startup():
    """Function that runs on application startup."""
    print("{{project_name_title}} starting up...")


@app.on_shutdown
async def shutdown():
    """Function that runs on application shutdown."""
    print("{{project_name_title}} shutting down...")


app.add_route(
    Route("/", index, summary="Homepage route", description="Homepage route"),
)
