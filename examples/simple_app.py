#!/usr/bin/env python3
"""
Simple Nexios application example.

This demonstrates the correct way to use app.run() when deployed to PyPI.
The app.run() method now uses uvicorn.run(app, ...) directly instead of
creating temporary files, which fixes the import error.
"""

from nexios import NexiosApp
from nexios.http import Request, Response

# Create the application
app = NexiosApp(
    title="Simple Nexios App",
    version="1.0.0",
    description="A simple example of Nexios usage",
)


@app.get("/")
async def home(request: Request, response: Response):
    """Home endpoint"""
    return response.json(
        {"message": "Welcome to Nexios!", "framework": "Nexios", "version": "1.0.0"}
    )


@app.get("/users/{user_id:int}")
async def get_user(request: Request, response: Response):
    """Get user by ID"""
    user_id = request.path_params.user_id
    return response.json(
        {
            "user_id": user_id,
            "name": f"User {user_id}",
            "email": f"user{user_id}@example.com",
        }
    )


@app.post("/users")
async def create_user(request: Request, response: Response):
    """Create a new user"""
    user_data = request.json
    return response.json(
        {"message": "User created successfully", "user": user_data}, status=201
    )


if __name__ == "__main__":
    print("Starting Simple Nexios App...")
    print("This app demonstrates the correct usage of app.run()")
    print("The method now uses uvicorn.run(app, ...) directly")
    print("This fixes the import error when deployed to PyPI")

    # This should work correctly now
    app.run(host="127.0.0.1", port=8000)
