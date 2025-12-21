# Group

The `Group` class in Nexios provides a way to organize and mount sub-applications or collections of routes under a common path prefix. It acts as a mounting point that can contain either an ASGI application or a collection of routes, with support for middleware and path parameter handling.

## 📋 Class Definition

```python
class Group(BaseRoute):
    def __init__(
        self,
        path: str = "",
        app: Optional[ASGIApp] = None,
        routes: Optional[List[BaseRoute]] = None,
        name: Optional[str] = None,
        *,
        middleware: List[Middleware] = [],
    )
```

## ⚙️ Constructor Parameters

### path: str
**Type**: `str`  
**Default**: `""`

The URL path prefix where the group will be mounted. Must start with "/" if provided.

```python
# Mount at root
root_group = Group(path="")

# Mount with prefix
api_group = Group(path="/api")
admin_group = Group(path="/admin")
```

### app: Optional[ASGIApp]
**Type**: `ASGIApp`  
**Default**: `None`

An ASGI application to mount at the specified path. This can be any ASGI-compatible application, including other Nexios apps, FastAPI apps, or custom ASGI applications.

```python
from nexios import NexiosApp

# Create a sub-application
sub_app = NexiosApp()

@sub_app.get("/health")
async def health_check(request, response):
    return response.json({"status": "ok"})

# Mount the sub-application
api_group = Group(path="/api/v1", app=sub_app)
```

### routes: Optional[List[BaseRoute]]
**Type**: `List[BaseRoute]`  
**Default**: `None`

A list of routes to be grouped together. When provided, a Router is automatically created to handle these routes.

```python
from nexios.routing import Route

# Define routes
health_route = Route("/health", health_handler, methods=["GET"])
status_route = Route("/status", status_handler, methods=["GET"])

# Group routes together
monitoring_group = Group(
    path="/monitoring",
    routes=[health_route, status_route]
)
```

### name: Optional[str]
**Type**: `str`  
**Default**: `None`

A unique identifier for the group, used for URL generation and route resolution.

```python
api_group = Group(
    path="/api/v1",
    routes=api_routes,
    name="api_v1"
)

# Generate URLs using the group name
url = api_group.url_path_for("api_v1", path="/users")
```

### middleware: List[Middleware]
**Type**: `List[Middleware]`  
**Default**: `[]`

Middleware that applies to all routes within the group. Middleware is applied in reverse order (last middleware wraps first).

```python
async def auth_middleware(request, response, call_next):
    # Authentication logic
    if not request.headers.get("authorization"):
        return response.status(401).json({"error": "Unauthorized"})
    return await call_next()

async def logging_middleware(request, response, call_next):
    print(f"Request: {request.method} {request.url}")
    return await call_next()

protected_group = Group(
    path="/protected",
    routes=protected_routes,
    middleware=[
        Middleware(auth_middleware),
        Middleware(logging_middleware)
    ]
)
```

## 💡 Usage Examples

### Basic Route Grouping

```python
from nexios import NexiosApp
from nexios.routing import Router, Route, Group

app = NexiosApp()

# Define handlers
async def list_users(request, response):
    users = await get_all_users()
    return response.json(users)

async def create_user(request, response):
    user_data = await request.json
    user = await create_user_service(user_data)
    return response.status(201).json(user)

async def get_user(request, response):
    user_id = request.path_params["user_id"]
    user = await get_user_by_id(user_id)
    return response.json(user)

# Create routes
user_routes = [
    Route("/", list_users, methods=["GET"]),
    Route("/", create_user, methods=["POST"]),
    Route("/{user_id}", get_user, methods=["GET"])
]

# Group routes under /users prefix
users_group = Group(path="/users", routes=user_routes, name="users")

# Mount the group
app.mount(users_group)
```

### Mounting Sub-Applications

```python
# Create a separate application for admin functionality
admin_app = NexiosApp()

@admin_app.get("/dashboard")
async def admin_dashboard(request, response):
    return response.json({"dashboard": "admin_data"})

@admin_app.get("/users")
async def admin_users(request, response):
    users = await get_all_users_admin()
    return response.json(users)

# Mount admin app under /admin prefix
admin_group = Group(path="/admin", app=admin_app, name="admin")

# Mount to main app
main_app = NexiosApp()
main_app.mount(admin_group)
```

### API Versioning with Groups

```python
from nexios import NexiosApp
from nexios.routing import Group

app = NexiosApp()

# Version 1 API
v1_app = NexiosApp()

@v1_app.get("/users")
async def list_users_v1(request, response):
    users = await get_users_v1_format()
    return response.json(users)

# Version 2 API
v2_app = NexiosApp()

@v2_app.get("/users")
async def list_users_v2(request, response):
    users = await get_users_v2_format()
    return response.json({
        "data": users,
        "meta": {"version": "2.0", "count": len(users)}
    })

# Mount different API versions
v1_group = Group(path="/api/v1", app=v1_app, name="api_v1")
v2_group = Group(path="/api/v2", app=v2_app, name="api_v2")

app.mount(v1_group)
app.mount(v2_group)
```

### Middleware Application

```python
async def cors_middleware(request, response, call_next):
    response = await call_next()
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE")
    return response

async def rate_limit_middleware(request, response, call_next):
    # Rate limiting logic
    client_ip = request.client.host
    if await is_rate_limited(client_ip):
        return response.status(429).json({"error": "Rate limit exceeded"})
    return await call_next()

# Apply middleware to all routes in the group
api_group = Group(
    path="/api",
    routes=api_routes,
    middleware=[
        Middleware(cors_middleware),
        Middleware(rate_limit_middleware)
    ],
    name="api"
)
```

## 🛣️ Path Parameter Handling

Groups support path parameters that can be captured and passed to the mounted application:

```python
# Group with path parameter
tenant_group = Group(
    path="/tenant/{tenant_id}",
    app=tenant_app,
    name="tenant"
)

# The tenant_app will receive the remaining path
# Request to /tenant/123/users -> tenant_app receives /users
# tenant_id is available in path_params
```

## 🔗 URL Generation

### Basic URL Generation

```python
users_group = Group(path="/users", routes=user_routes, name="users")

# Generate URL for the group
base_url = users_group.url_path_for("users", path="/")  # "/users/"
user_url = users_group.url_path_for("users", path="/123")  # "/users/123"
```

### URL Generation with Parameters

```python
tenant_group = Group(
    path="/tenant/{tenant_id}",
    app=tenant_app,
    name="tenant"
)

# Generate URL with path parameters
tenant_url = tenant_group.url_path_for(
    "tenant",
    tenant_id="abc123",
    path="/dashboard"
)  # "/tenant/abc123/dashboard"
```

## 🎯 Route Matching

The Group class implements sophisticated path matching:

```python
# Example group mounted at /api/v1
api_group = Group(path="/api/v1", app=sub_app)

# Request matching process:
# 1. Incoming request: GET /api/v1/users/123
# 2. Group matches /api/v1 prefix
# 3. Remaining path /users/123 is passed to sub_app
# 4. sub_app processes /users/123
```

## 🔧 Integration with Router

Groups work seamlessly with the Router class:

```python
from nexios.routing import Router, Group

# Create a router with routes
user_router = Router()

@user_router.get("/")
async def list_users(request, response):
    return response.json({"users": []})

@user_router.post("/")
async def create_user(request, response):
    user_data = await request.json
    return response.status(201).json(user_data)

# Mount router in a group
users_group = Group(path="/users", app=user_router, name="users")

# Or use routes directly
users_group_alt = Group(
    path="/users",
    routes=user_router.routes,
    name="users_alt"
)
app.add_route(users_group)
app.add_route(users_group_alt)
```


## 📊 Properties

### routes: List[BaseRoute]
Access the routes within the group (if using routes parameter).

```python
users_group = Group(path="/users", routes=user_routes)
print(f"Group has {len(users_group.routes)} routes")
```

### path: str
The group's mount path.

```python
api_group = Group(path="/api/v1", app=api_app)
print(f"Group mounted at: {api_group.path}")  # "/api/v1"
```

### name: Optional[str]
The group's name identifier.

```python
named_group = Group(path="/api", app=api_app, name="main_api")
print(f"Group name: {named_group.name}")  # "main_api"
```

## 🔍 See Also

- [Router](router.md) - Route organization and management
- [Route](route.md) - Individual route definitions
- [Middleware](middleware.md) - Request/response processing
- [NexiosApp](nexios-app.md) - Main application class