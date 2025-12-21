# NexiosApp

The `NexiosApp` class is the core application class in Nexios, serving as the main entry point for building web applications.

## 📋 Class Definition

```python
class NexiosApp:
    def __init__(
        self,
        config: Optional[MakeConfig] = DEFAULT_CONFIG,
        title: Optional[str] = None,
        version: Optional[str] = None,
        description: Optional[str] = None,
        server_error_handler: Optional[ServerErrHandlerType] = None,
        lifespan: Optional[lifespan_manager] = None,
        routes: Optional[List[Route]] = None,
        dependencies: Optional[list[Depend]] = None,
    )
```

## ⚙️ Constructor Parameters

### config: Optional[MakeConfig]
**Type**: `MakeConfig`  
**Default**: `DEFAULT_CONFIG`

Configuration object for the application. Manages all application settings including debug mode, database connections, and feature flags.

```python
from nexios import NexiosApp, MakeConfig

config = MakeConfig({
    "debug": True,
    "database_url": "postgresql://user:pass@localhost/db",
    "secret_key": "your-secret-key"
})

app = NexiosApp(config=config)
```

### title: Optional[str]
**Type**: `str`  
**Default**: `None`

The title of the API, used in OpenAPI documentation generation.

```python
app = NexiosApp(title="My API")
```

### version: Optional[str]
**Type**: `str`  
**Default**: `None`

The version of the API, displayed in OpenAPI documentation.

```python
app = NexiosApp(version="1.0.0")
```

### description: Optional[str]
**Type**: `str`  
**Default**: `None`

A brief description of the API for documentation purposes.

```python
app = NexiosApp(description="A powerful REST API built with Nexios")
```

### server_error_handler: Optional[ServerErrHandlerType]
**Type**: `ServerErrHandlerType`  
**Default**: `None`

Custom server error handler for managing exceptions and providing structured error responses.

```python
async def custom_error_handler(request, response, exc):
    return response.json({"error": str(exc)}, status_code=500)

app = NexiosApp(server_error_handler=custom_error_handler)
```

### lifespan: Optional[lifespan_manager]
**Type**: `Callable[[NexiosApp], AsyncContextManager[bool]]`  
**Default**: `None`

Lifespan context manager for handling application startup and shutdown events.

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Startup
    print("Application starting up...")
    yield
    # Shutdown
    print("Application shutting down...")

app = NexiosApp(lifespan=lifespan)
```

### routes: Optional[List[Route]]
**Type**: `List[Route]`  
**Default**: `None`

Initial list of routes to register with the application.

```python
from nexios.routing import Route

routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/users", get_users, methods=["GET"])
]

app = NexiosApp(routes=routes)
```

### dependencies: Optional[list[Depend]]
**Type**: `List[Depend]`  
**Default**: `None`

Global dependencies that will be injected into all route handlers.

```python
from nexios import Depend

async def get_db():
    return Database()

app = NexiosApp(dependencies=[Depend(get_db)])
```

## 🔧 Core Methods

### HTTP Route Decorators

#### get()
Register a GET endpoint with comprehensive OpenAPI support.

```python
@app.get(
    path="/users/{user_id}",
    summary="Get user by ID",
    description="Retrieve a specific user by their unique identifier",
    responses={
        200: UserResponse,
        404: {"description": "User not found"}
    },
    tags=["Users"]
)
async def get_user(request: Request, response: Response):
    user_id = request.path_params['user_id']
    user = await get_user_by_id(user_id)
    if not user:
        return response.status(404).json({"error": "User not found"})
    return response.json(user)
```

**Parameters**:
- `path` (str): URL path pattern with optional parameters
- `handler` (Optional[HandlerType]): Async handler function
- `name` (Optional[str]): Route name for URL generation
- `summary` (Optional[str]): Brief endpoint summary for docs
- `description` (Optional[str]): Detailed endpoint description
- `responses` (Optional[Dict[int, Any]]): Response models by status code
- `request_model` (Optional[Type[BaseModel]]): Pydantic model for validation
- `middleware` (List[Any]): Route-specific middleware
- `tags` (Optional[List[str]]): OpenAPI tags for grouping
- `security` (Optional[List[Dict[str, List[str]]]]): Security requirements
- `operation_id` (Optional[str]): Unique operation identifier
- `deprecated` (bool): Mark endpoint as deprecated
- `parameters` (List[Parameter]): Additional parameter definitions
- `exclude_from_schema` (bool): Exclude from OpenAPI docs

#### post()
Register a POST endpoint for creating resources.

```python
class CreateUserRequest(BaseModel):
    name: str
    email: str
    age: int

@app.post(
    "/users",
    request_model=CreateUserRequest,
    responses={201: UserResponse, 400: {"description": "Invalid input"}}
)
async def create_user(request: Request, response: Response):
    user_data = CreateUserRequest(**await request.json)
    user = await create_user_in_db(user_data)
    return response.status(201).json(user)
```

#### put()
Register a PUT endpoint for updating resources.

```python
@app.put("/users/{user_id}")
async def update_user(request: Request, response: Response):
    user_id = request.path_params['user_id']
    user_data = await request.json
    updated_user = await update_user_in_db(user_id, user_data)
    return response.json(updated_user)
```

#### delete()
Register a DELETE endpoint for removing resources.

```python
@app.delete("/users/{user_id}")
async def delete_user(request: Request, response: Response):
    user_id = request.path_params['user_id']
    await delete_user_from_db(user_id)
    return response.status(204).empty()
```

#### patch()
Register a PATCH endpoint for partial updates.

```python
@app.patch("/users/{user_id}")
async def patch_user(request: Request, response: Response):
    user_id = request.path_params['user_id']
    patch_data = await request.json
    user = await patch_user_in_db(user_id, patch_data)
    return response.json(user)
```

### Lifecycle Management

#### on_startup()
Register startup handlers that execute when the application starts.

```python
@app.on_startup
async def connect_to_database():
    global db
    db = await Database.connect("postgresql://...")
    print("Database connected")

@app.on_startup
async def initialize_cache():
    global cache
    cache = await Redis.connect("redis://...")
    print("Cache initialized")
```

#### on_shutdown()
Register shutdown handlers for cleanup when the application stops.

```python
@app.on_shutdown
async def disconnect_database():
    await db.disconnect()
    print("Database disconnected")

@app.on_shutdown
async def cleanup_cache():
    await cache.close()
    print("Cache cleaned up")
```

### Middleware Management

#### add_middleware()
Add HTTP middleware to the application.

```python
async def logging_middleware(request, response, call_next):
    start_time = time.time()
    result = await call_next()
    process_time = time.time() - start_time
    print(f"Request processed in {process_time:.4f}s")
    return result

app.add_middleware(logging_middleware)
```

#### add_ws_middleware()
Add WebSocket middleware to the application.

```python
async def ws_auth_middleware(websocket, call_next):
    token = websocket.headers.get("Authorization")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
    return await call_next()

app.add_ws_middleware(ws_auth_middleware)
```

### Router Management

#### mount_router()
Mount a router and all its routes to the application.

```python
from nexios.routing import Router

# Create a sub-router for user-related endpoints
user_router = Router(prefix="/api/v1/users")

@user_router.get("/")
async def list_users(request, response):
    users = await get_all_users()
    return response.json(users)

@user_router.get("/{user_id}")
async def get_user(request, response):
    user_id = request.path_params['user_id']
    user = await get_user_by_id(user_id)
    return response.json(user)

# Mount the router
app.mount_router(user_router, name="users")
```

#### mount_router()
Mount a WebSocket router to the application.

```python
from nexios.routing import Router

ws_router = Router(prefix="/ws")

@ws_router.ws("/chat")
async def chat_handler(websocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except Exception:
        await websocket.close()

app.mount_router(ws_router)
```

### WebSocket Routes

#### add_ws_route()
Add individual WebSocket routes.

```python
async def websocket_handler(websocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_text(f"Received: {message}")
    except Exception:
        await websocket.close()

app.add_ws_route(path="/ws/echo", handler=websocket_handler)
```

## 📊 Properties

### config
Access the application configuration.

```python
debug_mode = app.config.get("debug", False)
database_url = app.config.get("database_url")
```

### router
Access the main HTTP router.

```python
# Get all registered routes
routes = app.router.routes

# Add routes programmatically
app.router.add_route("/custom", custom_handler, methods=["GET"])
```

### ws_router
Access the WebSocket router.

```python
# Get all WebSocket routes
ws_routes = app.ws_router.routes
```

### state
Application-wide state dictionary.

```python
# Set application state
app.state["database"] = db_connection
app.state["cache"] = redis_connection

# Access in route handlers
async def get_data(request, response):
    db = request.app.state["database"]
    data = await db.fetch("SELECT * FROM items")
    return response.json(data)
```

### openapi_config
OpenAPI configuration object.

```python
# Customize OpenAPI settings
app.openapi_config.title = "Updated API Title"
app.openapi_config.version = "2.0.0"
app.openapi_config.add_security_scheme(
    "ApiKeyAuth",
    {"type": "apiKey", "in": "header", "name": "X-API-Key"}
)
```

## 🔌 ASGI Integration

The `NexiosApp` class implements the ASGI protocol and can be used with any ASGI server.

### With Uvicorn

```python
# main.py
from nexios import NexiosApp

app = NexiosApp(title="My API", version="1.0.0")

@app.get("/")
async def root(request, response):
    return response.json({"message": "Hello, World!"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### With Gunicorn

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### With Hypercorn

```bash
hypercorn main:app --bind 0.0.0.0:8000
```

## 🚀 Advanced Usage

### Custom Error Handling

```python
from nexios.exceptions import HTTPException

async def custom_error_handler(request, response, exc):
    if isinstance(exc, HTTPException):
        return response.status(exc.status_code).json({
            "error": exc.detail,
            "status_code": exc.status_code
        })
    
    # Log unexpected errors
    logger.error(f"Unexpected error: {exc}")
    return response.status(500).json({
        "error": "Internal server error",
        "status_code": 500
    })

app = NexiosApp(server_error_handler=custom_error_handler)
```

### Global Dependencies

```python
from nexios import Depend

async def get_current_user(request):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(401, "Authentication required")
    return await verify_token(token)

async def get_database():
    return Database()

# Global dependencies applied to all routes
app = NexiosApp(dependencies=[
    Depend(get_database),
    Depend(get_current_user)
])

@app.get("/protected")
async def protected_route(request, response, user=Depend(get_current_user), db=Depend(get_database)):
    # user and db are automatically injected
    data = await db.get_user_data(user.id)
    return response.json(data)
```

### Environment-based Configuration

```python
import os
from nexios import NexiosApp, MakeConfig

config = MakeConfig({
    "debug": os.getenv("DEBUG", "false").lower() == "true",
    "database_url": os.getenv("DATABASE_URL"),
    "redis_url": os.getenv("REDIS_URL"),
    "secret_key": os.getenv("SECRET_KEY"),
})

app = NexiosApp(
    config=config,
    title=os.getenv("API_TITLE", "My API"),
    version=os.getenv("API_VERSION", "1.0.0")
)
```

## 🔧 Internal Methods

### __call__()
ASGI application callable that handles incoming requests.

```python
async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    # Internal ASGI handling - not called directly
```

### handle_lifespan()
Handle ASGI lifespan protocol events.

```python
async def handle_lifespan(self, receive: Receive, send: Send) -> None:
    # Internal lifespan management - not called directly
```

### handle_http_request()
Process HTTP requests through the middleware stack.

```python
def handle_http_request(self, scope: Scope, receive: Receive, send: Send):
    # Internal HTTP request handling - not called directly
```

### handle_websocket()
Process WebSocket connections.

```python
async def handle_websocket(self, scope: Scope, receive: Receive, send: Send) -> None:
    # Internal WebSocket handling - not called directly
```

## ✨ Best Practices

1. **Configuration Management**: Use environment variables and the `MakeConfig` class for configuration
2. **Error Handling**: Implement custom error handlers for better user experience
3. **Middleware Order**: Add middleware in the correct order (auth before business logic)
4. **Dependencies**: Use dependency injection for database connections and shared resources
5. **Documentation**: Provide comprehensive OpenAPI documentation with examples
6. **Testing**: Use the built-in test client for comprehensive testing
7. **Lifecycle Management**: Properly handle startup and shutdown for resource management

## 🔍 See Also

- [Router](./router.md) - HTTP routing system
- [Middleware](./middleware.md) - Middleware development
- [Dependencies](./depend.md) - Dependency injection system
- [WebSocket](./websocket.md) - WebSocket handling