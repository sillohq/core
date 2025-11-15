# Route

The `Route` class represents individual HTTP routes in Nexios, providing detailed configuration options for path patterns, HTTP methods, middleware, dependencies, and OpenAPI documentation.

## 📋 Class Definition

```python
class Route(BaseRoute):
    def __init__(
        self,
        path: str,
        handler: HandlerType,
        methods: List[str] = ["GET"],
        name: Optional[str] = None,
        middleware: List[Middleware] = [],
        dependencies: List[Depend] = [],
        summary: Optional[str] = None,
        description: Optional[str] = None,
        responses: Optional[Dict[int, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Dict[str, Any]
    )
```

## ⚙️ Constructor Parameters

### path: str
**Type**: `str`  
**Required**: Yes

URL path pattern for the route. Supports path parameters using `{param}` syntax with optional type converters.

```python
# Basic path
Route("/users", list_users)

# Path with parameter
Route("/users/{user_id}", get_user)

# Path with typed parameter
Route("/users/{user_id:int}", get_user)

# Path with multiple parameters
Route("/users/{user_id:int}/posts/{post_id:int}", get_user_post)

# Path with wildcard
Route("/files/{file_path:path}", serve_file)
```

### handler: HandlerType
**Type**: `Callable[..., Awaitable[Any]]`  
**Required**: Yes

Async function that handles requests for this route.

```python
async def user_handler(request: Request, response: Response):
    user_id = request.path_params.get("user_id")
    user = await get_user_by_id(user_id)
    return response.json(user)

route = Route("/users/{user_id}", user_handler)
```

### methods: List[str]
**Type**: `List[str]`  
**Default**: `["GET"]`

HTTP methods that this route accepts.

```python
# Single method (default)
Route("/users", list_users, methods=["GET"])

# Multiple methods
Route("/users/{user_id}", user_handler, methods=["GET", "PUT", "DELETE"])

# All common methods
Route("/api/endpoint", api_handler, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
```

### name: Optional[str]
**Type**: `str`  
**Default**: `None`

Unique identifier for the route, used for URL generation.

```python
route = Route("/users/{user_id}", get_user, name="get_user")

# Generate URL using name
url = router.url_for("get_user", user_id=123)  # "/users/123"
```

### middleware: List[Middleware]
**Type**: `List[Middleware]`  
**Default**: `[]`

Route-specific middleware that applies only to this route.

```python
async def auth_required(request, response, call_next):
    if not request.user:
        return response.status(401).json({"error": "Authentication required"})
    return await call_next()

async def admin_required(request, response, call_next):
    if not request.user.is_admin:
        return response.status(403).json({"error": "Admin access required"})
    return await call_next()

route = Route(
    "/admin/users",
    admin_users_handler,
    middleware=[auth_required, admin_required]
)
```

### dependencies: List[Depend]
**Type**: `List[Depend]`  
**Default**: `[]`

Route-specific dependencies that will be injected into the handler.

```python
async def get_admin_user():
    return AdminUser()

async def get_audit_logger():
    return AuditLogger()

route = Route(
    "/admin/action",
    admin_action_handler,
    dependencies=[Depend(get_admin_user), Depend(get_audit_logger)]
)
```

## 📖 OpenAPI Documentation Parameters

### summary: Optional[str]
Brief summary of what the route does.

```python
route = Route(
    "/users/{user_id}",
    get_user,
    summary="Get user by ID"
)
```

### description: Optional[str]
Detailed description of the route's functionality.

```python
route = Route(
    "/users/{user_id}",
    get_user,
    summary="Get user by ID",
    description="Retrieve a specific user by their unique identifier. Returns user profile information including name, email, and account status."
)
```

### responses: Optional[Dict[int, Any]]
Expected response schemas by HTTP status code.

```python
from pydantic import BaseModel

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

class ErrorResponse(BaseModel):
    error: str
    code: str

route = Route(
    "/users/{user_id}",
    get_user,
    responses={
        200: UserResponse,
        404: ErrorResponse,
        500: {"description": "Internal server error"}
    }
)
```

### tags: Optional[List[str]]
OpenAPI tags for grouping related routes.

```python
route = Route(
    "/users/{user_id}",
    get_user,
    tags=["Users", "Public API"]
)
```

## 🛣️ Path Parameter Types

### String Parameters (default)
```python
# Matches any string (except '/')
Route("/users/{username}", get_user_by_name)

# In handler:
# username = request.path_params["username"]  # type: str
```

### Integer Parameters
```python
# Matches integers only
Route("/users/{user_id:int}", get_user)

# In handler:
# user_id = request.path_params["user_id"]  # type: int
```

### Float Parameters
```python
# Matches floating-point numbers
Route("/products/{price:float}", get_products_by_price)

# In handler:
# price = request.path_params["price"]  # type: float
```

### Path Parameters
```python
# Matches any path (including '/')
Route("/files/{file_path:path}", serve_file)

# In handler:
# file_path = request.path_params["file_path"]  # type: str
# Example: "/files/documents/report.pdf" -> file_path = "documents/report.pdf"
```

### UUID Parameters
```python
# Matches UUID format
Route("/resources/{resource_id:uuid}", get_resource)

# In handler:
# resource_id = request.path_params["resource_id"]  # type: str (UUID format)
```

## 🎯 Route Matching

### match()
Check if a path matches this route's pattern.

```python
route = Route("/users/{user_id:int}", get_user)

# Test matching
match_result = route.match("/users/123", "GET")
if match_result:
    match, params, is_match = match_result
    print(params)  # {"user_id": 123}
```

### Path Priority
Routes are matched in the order they're registered. More specific routes should be registered first.

```python
# Correct order - specific to general
routes = [
    Route("/users/me", get_current_user),           # Specific
    Route("/users/{user_id:int}", get_user),        # Less specific
    Route("/users/{username}", get_user_by_name),   # Most general
]
```

## 🚀 Advanced Route Configuration

### Custom Converters
```python
class SlugConverter:
    regex = r"[a-z0-9]+(?:-[a-z0-9]+)*"
    
    def convert(self, value: str) -> str:
        return value
    
    def to_string(self, value: str) -> str:
        return value

# Register custom converter
app.router.add_converter("slug", SlugConverter)

# Use in route
Route("/posts/{slug:slug}", get_post_by_slug)
```

### Conditional Routes
```python
async def conditional_handler(request: Request, response: Response):
    # Different behavior based on conditions
    if request.headers.get("Accept") == "application/json":
        return response.json({"data": "json_response"})
    else:
        return response.html("<h1>HTML Response</h1>")

route = Route(
    "/data",
    conditional_handler,
    methods=["GET"],
    summary="Get data in multiple formats"
)
```

### Route with Validation
```python
from pydantic import BaseModel, ValidationError

class CreateUserRequest(BaseModel):
    name: str
    email: str
    age: int

async def create_user_handler(request: Request, response: Response):
    try:
        json_data = await request.json
        user_data = CreateUserRequest(**json_data)
        
        # Create user with validated data
        user = await create_user_service(user_data)
        return response.status(201).json(user)
        
    except ValidationError as e:
        return response.status(400).json({
            "error": "Validation failed",
            "details": e.errors()
        })

route = Route(
    "/users",
    create_user_handler,
    methods=["POST"],
    summary="Create new user",
    responses={
        201: {"description": "User created successfully"},
        400: {"description": "Validation error"}
    }
)
```

## 📁 Route Groups and Organization

### Grouping Related Routes
```python
# User management routes
user_routes = [
    Route("/", list_users, methods=["GET"], name="list_users"),
    Route("/", create_user, methods=["POST"], name="create_user"),
    Route("/{user_id:int}", get_user, methods=["GET"], name="get_user"),
    Route("/{user_id:int}", update_user, methods=["PUT"], name="update_user"),
    Route("/{user_id:int}", delete_user, methods=["DELETE"], name="delete_user"),
]

# Create router with routes
user_router = Router(prefix="/users", routes=user_routes)
```

### Route Inheritance
```python
class BaseRoute(Route):
    def __init__(self, path: str, handler: HandlerType, **kwargs):
        # Add common middleware and dependencies
        common_middleware = [auth_middleware, logging_middleware]
        common_dependencies = [Depend(get_database)]
        
        middleware = kwargs.get("middleware", [])
        dependencies = kwargs.get("dependencies", [])
        
        kwargs["middleware"] = common_middleware + middleware
        kwargs["dependencies"] = common_dependencies + dependencies
        
        super().__init__(path, handler, **kwargs)

# Use base route
route = BaseRoute("/protected", protected_handler)
```

## ⚠️ Error Handling in Routes

### Route-specific Error Handling
```python
async def safe_handler(request: Request, response: Response):
    try:
        # Route logic
        result = await process_request(request)
        return response.json(result)
        
    except ValidationError as e:
        return response.status(400).json({
            "error": "Invalid input",
            "details": str(e)
        })
    except PermissionError:
        return response.status(403).json({
            "error": "Access denied"
        })
    except Exception as e:
        logger.error(f"Unexpected error in route: {e}")
        return response.status(500).json({
            "error": "Internal server error"
        })

route = Route("/safe-endpoint", safe_handler)
```

### Custom Exception Classes
```python
class RouteException(Exception):
    def __init__(self, status_code: int, message: str, details: dict = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}

async def handler_with_custom_exceptions(request: Request, response: Response):
    user_id = request.path_params.get("user_id")
    
    if not user_id:
        raise RouteException(400, "User ID is required")
    
    user = await get_user(user_id)
    if not user:
        raise RouteException(404, "User not found", {"user_id": user_id})
    
    return response.json(user)

# Error handling middleware would catch RouteException
async def route_error_middleware(request, response, call_next):
    try:
        return await call_next()
    except RouteException as e:
        return response.status(e.status_code).json({
            "error": e.message,
            "details": e.details
        })
```

## 🧪 Testing Routes

### Unit Testing Individual Routes
```python
import pytest
from nexios.testing import TestClient

@pytest.mark.asyncio
async def test_get_user_route():
    # Create route
    route = Route("/users/{user_id:int}", get_user, name="get_user")
    
    # Create app with route
    app = NexiosApp()
    app.router.add_route(route)
    
    # Test route
    async with TestClient(app) as client:
        response = await client.get("/users/123")
        assert response.status_code == 200
        assert response.json()["user_id"] == 123
```

### Testing Route Matching
```python
def test_route_matching():
    route = Route("/users/{user_id:int}/posts/{post_id:int}", handler)
    
    # Test valid match
    match_result = route.match("/users/123/posts/456", "GET")
    assert match_result is not None
    match, params, is_match = match_result
    assert params == {"user_id": 123, "post_id": 456}
    
    # Test invalid match
    match_result = route.match("/users/abc/posts/456", "GET")
    assert match_result is None
```

### Testing Route Parameters
```python
@pytest.mark.asyncio
async def test_route_parameters():
    async def test_handler(request, response):
        user_id = request.path_params["user_id"]
        return response.json({"user_id": user_id, "type": type(user_id).__name__})
    
    route = Route("/users/{user_id:int}", test_handler)
    app = NexiosApp()
    app.router.add_route(route)
    
    async with TestClient(app) as client:
        response = await client.get("/users/123")
        data = response.json()
        assert data["user_id"] == 123
        assert data["type"] == "int"
```

## ⚡ Performance Considerations

### Route Compilation
Routes are compiled into regex patterns for efficient matching.

```python
# This route pattern:
"/users/{user_id:int}/posts/{post_id:int}"

# Is compiled to a regex pattern for fast matching
# The compilation happens once when the route is registered
```

### Route Caching
```python
# For frequently accessed routes, consider caching
async def cached_handler(request: Request, response: Response):
    cache_key = f"route:{request.path}:{request.query_string}"
    
    # Try cache first
    cached_result = await cache.get(cache_key)
    if cached_result:
        return response.json(cached_result)
    
    # Generate result
    result = await expensive_operation()
    
    # Cache result
    await cache.set(cache_key, result, ttl=300)
    
    return response.json(result)
```

## ✨ Best Practices

1. **Use descriptive route names** for URL generation
2. **Order routes from specific to general** to avoid matching issues
3. **Use appropriate HTTP methods** for different operations
4. **Include comprehensive OpenAPI documentation** for better API docs
5. **Handle errors gracefully** with proper status codes
6. **Use typed path parameters** when possible for validation
7. **Group related routes** using routers with prefixes
8. **Test routes thoroughly** including edge cases
9. **Use middleware for cross-cutting concerns** like authentication
10. **Keep handlers focused** on a single responsibility

## 🔄 Route Lifecycle

### Registration
```python
# 1. Route is created
route = Route("/users/{user_id}", get_user)

# 2. Route is added to router
router.add_route(route)

# 3. Route pattern is compiled
# 4. Route is ready to handle requests
```

### Request Processing
```python
# 1. Incoming request matches route pattern
# 2. Path parameters are extracted and converted
# 3. Route middleware is executed
# 4. Dependencies are resolved and injected
# 5. Handler is called with request, response, and dependencies
# 6. Response is returned
```

## 🔍 See Also

- [Router](./router.md) - Route organization and management
- [Groups](./groups.md) - Route grouping strategies
- [URL Generation](./url-generation.md) - Generating URLs from routes
- [Middleware](../middleware/base.md) - Route middleware
- [Dependencies](../dependencies/depend.md) - Route dependencies
- [OpenAPI](../openapi/builder.md) - Route documentation