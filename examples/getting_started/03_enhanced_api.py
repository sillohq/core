"""
Enhanced Nexios API Demo - Showcasing Comprehensive Documentation

This example demonstrates the enhanced Nexios framework with comprehensive
docstrings, type annotations, and user-friendly API design.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr

from nexios import Depend, MakeConfig, NexiosApp
from nexios.http import Request, Response
from nexios.routing import Router
from nexios.views import APIView
from nexios.websockets import WebSocket, WebSocketDisconnect


# Pydantic models for request/response validation
class UserCreate(BaseModel):
    """Model for creating a new user."""

    name: str
    email: EmailStr
    age: Optional[int] = None


class UserResponse(BaseModel):
    """Model for user response data."""

    id: int
    name: str
    email: str
    age: Optional[int]
    created_at: datetime


class ChatMessage(BaseModel):
    """Model for chat messages."""

    user: str
    message: str
    timestamp: datetime


# Dependency injection examples
def get_database():
    """
    Database dependency provider.

    In a real application, this would return a database connection
    or session that can be used throughout the request lifecycle.
    """
    return {"connection": "mock_database"}


async def get_current_user(request: Request = Depend(lambda: None)):
    """
    Get the current authenticated user from the request.

    This dependency extracts user information from the Authorization header
    and returns the user object, or raises an exception if not authenticated.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    # In a real app, you'd validate the token and fetch the user
    return {"id": 1, "name": "John Doe", "email": "john@example.com"}


# Class-based views example
class UserView(APIView):
    """
    Class-based view for user management endpoints.

    This view demonstrates how to organize related HTTP methods
    in a single class with shared middleware and error handling.
    """

    # Middleware applied to all methods in this view
    middleware = []  # Add authentication, rate limiting, etc.

    # Custom error handlers for this view
    error_handlers = {}

    async def get(self, request: Request, response: Response):
        """Get all users with optional filtering."""
        # Access query parameters
        limit = int(request.query_params.get("limit", "10"))
        offset = int(request.query_params.get("offset", "0"))

        # Mock user data
        users = [
            {
                "id": i,
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "age": 25 + i,
                "created_at": datetime.now().isoformat(),
            }
            for i in range(offset + 1, offset + limit + 1)
        ]

        return response.json(
            {"users": users, "total": 100, "limit": limit, "offset": offset}
        )

    async def post(self, request: Request, response: Response):
        """Create a new user."""
        # Parse and validate JSON data
        data = await request.json

        try:
            user_data = UserCreate(**data)
        except Exception as e:
            return response.json(
                {"error": "Invalid user data", "details": str(e)}, status=400
            )

        # Create user (mock)
        new_user = {
            "id": 123,
            "name": user_data.name,
            "email": user_data.email,
            "age": user_data.age,
            "created_at": datetime.now().isoformat(),
        }

        return response.json(new_user, status=201)


# Function-based route handlers
async def get_user_detail(
    request: Request,
    response: Response,
    db=Depend(get_database),
    current_user=Depend(get_current_user),
):
    """
    Get detailed information about a specific user.

    This endpoint demonstrates:
    - Path parameter extraction
    - Dependency injection
    - Error handling
    - Response customization
    """
    user_id = request.path_params.get("id")

    if not user_id:
        return response.json({"error": "User ID is required"}, status=400)

    # Mock user lookup
    if user_id == "999":
        return response.json({"error": "User not found"}, status=404)

    user = {
        "id": int(user_id),
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com",
        "age": 30,
        "created_at": datetime.now().isoformat(),
        "profile": {
            "bio": "This is a sample user profile",
            "location": "San Francisco, CA",
        },
    }

    # Add custom headers
    return (
        response.json(user).set_header("X-User-ID", user_id).cache(max_age=300)
    )  # Cache for 5 minutes


async def upload_file(request: Request, response: Response):
    """
    Handle file uploads with validation and processing.

    This endpoint demonstrates:
    - File upload handling
    - Content type validation
    - Custom response headers
    """
    if not request.is_multipart:
        return response.json({"error": "Multipart form data required"}, status=400)

    files = await request.files
    uploaded_file = files.get("file")

    if not uploaded_file:
        return response.json({"error": "No file uploaded"}, status=400)

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif"]
    if uploaded_file.content_type not in allowed_types:
        return response.json(
            {"error": f"File type {uploaded_file.content_type} not allowed"}, status=400
        )

    # Process file (mock)
    file_info = {
        "filename": uploaded_file.filename,
        "size": len(await uploaded_file.read()),
        "content_type": uploaded_file.content_type,
        "upload_id": "abc123",
        "url": f"/files/abc123/{uploaded_file.filename}",
    }

    return response.json(file_info, status=201).set_header("X-Upload-ID", "abc123")


# WebSocket handler example
async def chat_websocket(websocket: WebSocket):
    """
    WebSocket handler for real-time chat functionality.

    This handler demonstrates:
    - WebSocket connection management
    - Message broadcasting
    - Error handling
    - Connection cleanup
    """
    room_id = websocket.path_params.get("room_id", "general")

    await websocket.accept()

    # Send welcome message
    await websocket.send_json(
        {
            "type": "welcome",
            "message": f"Welcome to room {room_id}!",
            "timestamp": datetime.now().isoformat(),
        }
    )

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            # Validate message
            try:
                message = ChatMessage(**data)
            except Exception:
                await websocket.send_json(
                    {"type": "error", "message": "Invalid message format"}
                )
                continue

            # Echo message back (in real app, broadcast to room)
            await websocket.send_json(
                {
                    "type": "message",
                    "user": message.user,
                    "message": message.message,
                    "timestamp": message.timestamp.isoformat(),
                    "room": room_id,
                }
            )

    except WebSocketDisconnect:
        print(f"Client disconnected from room {room_id}")


# Create application with enhanced configuration
def create_app() -> NexiosApp:
    """
    Create and configure the Nexios application.

    This function demonstrates:
    - Application configuration
    - Route registration
    - Middleware setup
    - OpenAPI documentation
    """

    # Create configuration with validation
    config = MakeConfig(
        {
            "debug": True,
            "database": {"url": "postgresql://localhost/nexios_demo", "pool_size": 10},
            "redis": {"url": "redis://localhost:6379", "max_connections": 20},
        }
    )

    # Create application with OpenAPI documentation
    app = NexiosApp(
        config=config,
        title="Enhanced Nexios API Demo",
        version="1.0.0",
        description="Demonstration of Nexios framework with comprehensive documentation",
    )

    # Register class-based view
    app.add_route(
        UserView.as_route(
            "/users",
            name="user-list",
            tags=["Users"],
            summary="User management endpoints",
        )
    )

    # Register function-based routes with full OpenAPI documentation
    app.get(
        "/users/{id}",
        handler=get_user_detail,
        name="user-detail",
        summary="Get user by ID",
        description="Retrieve detailed information about a specific user",
        tags=["Users"],
        responses={
            200: UserResponse,
            404: {"description": "User not found"},
            400: {"description": "Invalid user ID"},
        },
    )

    app.post(
        "/upload",
        handler=upload_file,
        name="file-upload",
        summary="Upload file",
        description="Upload and process files with validation",
        tags=["Files"],
        responses={
            201: {"description": "File uploaded successfully"},
            400: {"description": "Invalid file or format"},
        },
    )

    # Register WebSocket route
    app.ws_route("/ws/chat/{room_id}", chat_websocket)

    # Add global middleware (example)
    @app.add_middleware
    async def logging_middleware(request: Request, response: Response, call_next):
        """Log all requests with timing information."""
        start_time = datetime.now()

        # Process request
        result = await call_next()

        # Log request details
        duration = (datetime.now() - start_time).total_seconds()
        print(
            f"{request.method} {request.url} - {response.status_code} ({duration:.3f}s)"
        )

        return result

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    # Run the application
    print("Starting Enhanced Nexios API Demo...")
    print("Visit http://localhost:8000/docs for interactive API documentation")
    print("WebSocket chat available at ws://localhost:8000/ws/chat/general")

    app.run(host="0.0.0.0", port=8000, reload=True)
