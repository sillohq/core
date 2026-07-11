from routes.index.route import index_router

from sillo import silloApp
from sillo.templating import TemplateEngine, render

app = silloApp()
engine = TemplateEngine()
engine.setup_environment()


app.mount_router(index_router)


@app.on_startup
async def startup():
    """Function that runs on application startup."""
    print("{{project_name_title}} starting up...")


@app.on_shutdown
async def shutdown():
    """Function that runs on application shutdown."""
    print("{{project_name_title}} shutting down...")
