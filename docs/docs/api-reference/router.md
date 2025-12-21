# Router

The `Router` class is the core routing component in Nexios, responsible for organizing and managing HTTP routes with support for prefixes, middleware, dependencies, and sub-routers.

## 📋 Class Definition

```python
class Router(BaseRouter):
    def __init__(
        self,
        prefix: str = "",
        routes: Optional[List[Route]] = None,
        dependencies: Optional[List[Depend]] = None,
        middleware: Optional[List[Middleware]] = None,
        tags: Optional[List[str]] = None,
        responses: Optional[Dict[int, Any]] = None,
    )
```

## ⚙️ Constructor Parameters

### prefix: str
**Type**: `str`  
**Default**: `""`

URL prefix for all routes in this router. Must start with "/" if provided.

```python
# API versioning
api_v1 = Router(prefix="/api/v1")
api_v2 = Router(prefix="/api/v2")

# Feature grouping
user_router = Router(prefix="/users")
admin_router = Router(prefix="/admin")
```

### routes: Optional[List[Route]]
**Type**: `List[Route]`  
**Default**: `None`

Initial list of routes to register with the router.

```python
from nexios.routing import Route

initial_routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/status", status_check, methods=["GET"])
]

router = Router(prefix="/api", routes=initial_routes)
```

### dependencies: Optional[List[Depend]]
**Type**: `List[Depend]`  
**Default**: `None`

Dependencies that will be injected into all routes in this router.

```python
from nexios import Depend

async def get_db():
    return Database()

async def get_current_user():
    return User()

router = Router(
    prefix="/api",
    dependencies=[Depend(get_db), Depend(get_current_user)]
)
```

### middleware: Optional[List[Middleware]]
**Type**: `List[Middleware]`  
**Default**: `None`

Middleware that applies to all routes in this router.

```python
async def auth_middleware(request, response, call_next):
    # Authentication logic
    return await call_next()

router = Router(
    prefix="/protected",
    middleware=[auth_middleware]
)
```

### tags: Optional[List[str]]
**Type**: `List[str]`  
**Default**: `None`

OpenAPI tags applied to all routes in this router.

```python
router = Router(
    prefix="/users",
    tags=["Users", "Authentication"]
)
```

### responses: Optional[Dict[int, Any]]
**Type**: `Dict[int, Any]`  
**Default**: `None`

Common response schemas for all routes in this router.

```python
common_responses = {
    401: {"description": "Unauthorized"},
    403: {"description": "Forbidden"},
    500: {"description": "Internal Server Error"}
}

router = Router(
    prefix="/api",
    responses=common_responses
)
```

## 🛣️ Route Registration Methods

### get()
Register GET endpoint.

```python
@router.get("/users")
async def list_users(request: Request, response: Response):
    users = await get_all_users()
    return response.json(users)

@router.get("/users/{user_id}")
async def get_user(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    user = await get_user_by_id(user_id)
    return response.json(user)
```

### post()
Register POST endpoint.

```python
@router.post("/users")
async def create_user(request: Request, response: Response):
    user_data = await request.json
    user = await create_user_service(user_data)
    return response.status(201).json(user)
```

### put()
Register PUT endpoint.

```python
@router.put("/users/{user_id}")
async def update_user(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    user_data = await request.json
    user = await update_user_service(user_id, user_data)
    return response.json(user)
```

### delete()
Register DELETE endpoint.

```python
@router.delete("/users/{user_id}")
async def delete_user(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    await delete_user_service(user_id)
    return response.status(204).empty()
```

### patch()
Register PATCH endpoint.

```python
@router.patch("/users/{user_id}")
async def patch_user(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    patch_data = await request.json
    user = await patch_user_service(user_id, patch_data)
    return response.json(user)
```

### options()
Register OPTIONS endpoint.

```python
@router.options("/users")
async def users_options(request: Request, response: Response):
    return response.set_header("Allow", "GET, POST, OPTIONS").empty()
```

### head()
Register HEAD endpoint.

```python
@router.head("/users/{user_id}")
async def user_head(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    exists = await user_exists(user_id)
    if exists:
        return response.status(200).empty()
    else:
        return response.status(404).empty()
```

### route()
Register route with custom methods.

```python
@router.route("/users/{user_id}", methods=["GET", "PUT", "DELETE"])
async def user_handler(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    
    if request.method == "GET":
        user = await get_user_by_id(user_id)
        return response.json(user)
    elif request.method == "PUT":
        user_data = await request.json
        user = await update_user_service(user_id, user_data)
        return response.json(user)
    elif request.method == "DELETE":
        await delete_user_service(user_id)
        return response.status(204).empty()
```

## 🔧 Route Management

### add_route()
Programmatically add routes.

```python
async def custom_handler(request: Request, response: Response):
    return response.json({"message": "Custom route"})

router.add_route(
    path="/custom",
    handler=custom_handler,
    methods=["GET", "POST"],
    name="custom_route"
)
```

### mount_router()
Mount sub-routers.

```python
# Create sub-routers
user_router = Router(prefix="/users")
admin_router = Router(prefix="/admin")

@user_router.get("/")
async def list_users(request, response):
    return response.json({"users": []})

@admin_router.get("/dashboard")
async def admin_dashboard(request, response):
    return response.json({"dashboard": "data"})

# Mount sub-routers
main_router = Router(prefix="/api/v1")
main_router.mount_router(user_router, name="users")
main_router.mount_router(admin_router, name="admin")
```

## 🔗 Middleware Management

### add_middleware()
Add middleware to the router.

```python
async def logging_middleware(request, response, call_next):
    start_time = time.time()
    result = await call_next()
    duration = time.time() - start_time
    print(f"Request took {duration:.4f}s")
    return result

router.add_middleware(logging_middleware)
```

### Multiple Middleware
Middleware is applied in the order it's added.

```python
async def auth_middleware(request, response, call_next):
    # Authentication
    return await call_next()

async def rate_limit_middleware(request, response, call_next):
    # Rate limiting
    return await call_next()

router.add_middleware(auth_middleware)      # Applied first
router.add_middleware(rate_limit_middleware) # Applied second
```

## 💉 Dependency Injection

### Router-level Dependencies
Dependencies applied to all routes in the router.

```python
async def get_database():
    return Database()

async def get_cache():
    return Cache()

router = Router(
    prefix="/api",
    dependencies=[Depend(get_database), Depend(get_cache)]
)

@router.get("/data")
async def get_data(request, response, db=Depend(get_database), cache=Depend(get_cache)):
    # db and cache are automatically injected
    cached_data = await cache.get("data")
    if not cached_data:
        cached_data = await db.fetch_data()
        await cache.set("data", cached_data)
    return response.json(cached_data)
```

### Route-specific Dependencies
Override or add dependencies for specific routes.

```python
async def get_admin_user():
    return AdminUser()

@router.get("/admin/users", dependencies=[Depend(get_admin_user)])
async def admin_users(request, response, admin=Depend(get_admin_user)):
    # Only admin users can access this route
    users = await get_all_users_admin(admin)
    return response.json(users)
```

## 🛣️ Path Parameters and Patterns

### Basic Path Parameters

```python
@router.get("/users/{user_id}")
async def get_user(request: Request, response: Response):
    user_id = request.path_params["user_id"]  # String by default
    return response.json({"user_id": user_id})
```

### Typed Path Parameters

```python
@router.get("/users/{user_id:int}")
async def get_user(request: Request, response: Response):
    user_id = request.path_params["user_id"]  # Automatically converted to int
    return response.json({"user_id": user_id})

@router.get("/files/{file_path:path}")
async def get_file(request: Request, response: Response):
    file_path = request.path_params["file_path"]  # Captures full path
    return response.file(f"/uploads/{file_path}")
```

### Multiple Parameters

```python
@router.get("/users/{user_id:int}/posts/{post_id:int}")
async def get_user_post(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    post_id = request.path_params["post_id"]
    
    post = await get_post(user_id, post_id)
    return response.json(post)
```

## 🔗 URL Generation

### url_for()
Generate URLs for named routes.

```python
@router.get("/users/{user_id}", name="get_user")
async def get_user(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    user = await get_user_by_id(user_id)
    return response.json(user)

# Generate URL
user_url = router.url_for("get_user", user_id=123)  # "/users/123"
```

### Absolute URLs

```python
async def handler(request: Request, response: Response):
    # Generate absolute URL
    user_url = request.build_absolute_uri(
        router.url_for("get_user", user_id=123)
    )
    # "https://example.com/users/123"
    
    return response.json({"user_url": user_url})
```

## 📖 OpenAPI Integration

### Route Documentation

```python
@router.get(
    "/users/{user_id}",
    summary="Get user by ID",
    description="Retrieve a specific user by their unique identifier",
    responses={
        200: UserResponse,
        404: {"description": "User not found"}
    },
    tags=["Users"]
)
async def get_user(request: Request, response: Response):
    # Implementation
    pass
```

### Router-level Documentation

```python
router = Router(
    prefix="/users",
    tags=["Users"],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"}
    }
)
```

## 🚀 Advanced Routing Patterns

### Conditional Routing

```python
@router.get("/data")
async def get_data(request: Request, response: Response):
    # Content negotiation
    accept = request.headers.get("accept", "")
    
    data = await fetch_data()
    
    if "application/json" in accept:
        return response.json(data)
    elif "text/csv" in accept:
        csv_data = convert_to_csv(data)
        return response.text(csv_data, headers={"Content-Type": "text/csv"})
    else:
        return response.json(data)  # Default to JSON
```

### Versioned APIs

```python
# Version 1
v1_router = Router(prefix="/api/v1")

@v1_router.get("/users")
async def list_users_v1(request, response):
    users = await get_users_v1()
    return response.json(users)

# Version 2
v2_router = Router(prefix="/api/v2")

@v2_router.get("/users")
async def list_users_v2(request, response):
    users = await get_users_v2()
    return response.json({
        "data": users,
        "meta": {"version": "2.0"}
    })

# Mount both versions
app.mount_router(v1_router)
app.mount_router(v2_router)
```

### Resource-based Routing

```python
class UserRouter:
    def __init__(self):
        self.router = Router(prefix="/users")
        self._setup_routes()
    
    def _setup_routes(self):
        self.router.get("/")(self.list_users)
        self.router.post("/")(self.create_user)
        self.router.get("/{user_id}")(self.get_user)
        self.router.put("/{user_id}")(self.update_user)
        self.router.delete("/{user_id}")(self.delete_user)
    
    async def list_users(self, request, response):
        users = await self.user_service.get_all()
        return response.json(users)
    
    async def create_user(self, request, response):
        user_data = await request.json
        user = await self.user_service.create(user_data)
        return response.status(201).json(user)
    
    async def get_user(self, request, response):
        user_id = request.path_params["user_id"]
        user = await self.user_service.get_by_id(user_id)
        return response.json(user)
    
    async def update_user(self, request, response):
        user_id = request.path_params["user_id"]
        user_data = await request.json
        user = await self.user_service.update(user_id, user_data)
        return response.json(user)
    
    async def delete_user(self, request, response):
        user_id = request.path_params["user_id"]
        await self.user_service.delete(user_id)
        return response.status(204).empty()

# Usage
user_router = UserRouter()
app.mount_router(user_router.router)
```

## ⚠️ Error Handling

### Router-level Error Handling

```python
async def error_middleware(request, response, call_next):
    try:
        return await call_next()
    except ValidationError as e:
        return response.status(400).json({
            "error": "Validation failed",
            "details": e.errors()
        })
    except NotFoundError:
        return response.status(404).json({
            "error": "Resource not found"
        })
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return response.status(500).json({
            "error": "Internal server error"
        })

router.add_middleware(error_middleware)
```

### Custom Exception Handlers

```python
from nexios.exceptions import HTTPException

@router.get("/users/{user_id}")
async def get_user(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    
    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user ID format")
    
    user = await get_user_by_id(user_id_int)
    if not user:
        raise HTTPException(404, "User not found")
    
    return response.json(user)
```

## 🧪 Testing Router

### Unit Testing Routes

```python
import pytest
from nexios.testing import TestClient

@pytest.fixture
def client():
    router = Router()
    
    @router.get("/test")
    async def test_route(request, response):
        return response.json({"message": "test"})
    
    app = NexiosApp()
    app.mount_router(router)
    return TestClient(app)

def test_route(client):
    response = client.get("/test")
    assert response.status_code == 200
    assert response.json() == {"message": "test"}
```

### Integration Testing

```python
async def test_user_crud():
    router = Router(prefix="/users")
    
    # Setup routes
    @router.post("/")
    async def create_user(request, response):
        user_data = await request.json
        user = await create_user_service(user_data)
        return response.status(201).json(user)
    
    @router.get("/{user_id}")
    async def get_user(request, response):
        user_id = request.path_params["user_id"]
        user = await get_user_service(user_id)
        return response.json(user)
    
    app = NexiosApp()
    app.mount_router(router)
    
    async with TestClient(app) as client:
        # Create user
        create_response = await client.post("/users/", json={
            "name": "John Doe",
            "email": "john@example.com"
        })
        assert create_response.status_code == 201
        
        user_id = create_response.json()["id"]
        
        # Get user
        get_response = await client.get(f"/users/{user_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "John Doe"
```

## ⚡ Performance Considerations

### Route Ordering
More specific routes should be defined before general ones.

```python
# Correct order
@router.get("/users/me")          # Specific route first
async def get_current_user(request, response):
    pass

@router.get("/users/{user_id}")   # General route second
async def get_user(request, response):
    pass
```

### Middleware Optimization
Keep middleware lightweight and avoid heavy operations.

```python
async def fast_middleware(request, response, call_next):
    # Quick check
    if not request.headers.get("authorization"):
        return response.status(401).json({"error": "Unauthorized"})
    
    return await call_next()

async def heavy_middleware(request, response, call_next):
    # Expensive operation - use sparingly
    user = await complex_user_lookup(request)
    request.state.user = user
    return await call_next()
```

## ✨ Best Practices

1. **Use meaningful prefixes** for router organization
2. **Group related routes** in the same router
3. **Apply common middleware** at the router level
4. **Use dependencies** for shared resources
5. **Name your routes** for URL generation
6. **Document routes** with OpenAPI metadata
7. **Handle errors consistently** across the router
8. **Test routes thoroughly** with various inputs
9. **Order routes** from specific to general
10. **Keep middleware lightweight** for performance

## 📊 Router Properties

### routes: List[Route]
List of all routes registered with the router.

```python
router = Router()

@router.get("/test")
async def test_handler(request, response):
    pass

print(len(router.routes))  # 1
print(router.routes[0].path)  # "/test"
```

### prefix: str
The router's URL prefix.

```python
router = Router(prefix="/api/v1")
print(router.prefix)  # "/api/v1"
```

### middleware: List[Middleware]
List of middleware applied to the router.

```python
router = Router()
router.add_middleware(auth_middleware)
print(len(router.middleware))  # 1
```

## 🔍 See Also

- [Route](./route.md) - Individual route definitions
- [Groups](./group.md) - Route grouping and organization
- [Middleware](./middleware.md) - Middleware system
- [Dependencies](./depend.md) - Dependency injection
- [OpenAPI](./openapi-builder.md) - API documentation