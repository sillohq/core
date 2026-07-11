from sillo import silloApp
from sillo.http import Request, Response

# Create the application
app = silloApp(title="{{project_name_title}}")


# Define routes
@app.get("/")
async def index(request: Request, response: Response):
    """Homepage route."""
    return {"message": "Welcome to {{project_name_title}}!", "framework": "sillo"}
