---
title: OpenAPI Documentation
description: >
    sillo provides comprehensive, automatic API documentation powered by the OpenAPI 3.0 standard. Every route you define is automatically documented with interactive UIs, type validation, and professional-grade specifications.
---

#  OpenAPI Documentation

sillo provides comprehensive, automatic API documentation powered by the OpenAPI 3.0 standard. Every route you define is automatically documented with interactive UIs, type validation, and professional-grade specifications.

##  Quick Start

By default, sillo generates complete OpenAPI documentation for all your routes:

```python
from sillo import SilloApp, HttpContext, json

app = SilloApp(
    title="My API",
    version="1.0.0", 
    description="A comprehensive API built with sillo"
)

@app.get("/users/{user_id}")
async def get_user(ctx: HttpContext, user_id: int):
    """Retrieve a user by their ID."""
    return json({"id": user_id, "name": "John Doe"})
```

This automatically creates:
- **Atlas**, sillo's own reference, at `/docs`
- **ReDoc documentation** at `/redoc`
- **OpenAPI JSON specification** at `/openapi.json`

##  Documentation Interfaces

sillo provides multiple ways to explore your API. Which viewers are mounted is
the `docs` argument: Atlas and ReDoc by default, plus Swagger UI, Scalar and
anything you write yourself. See [Documentation
UI](/v1.0/guides/openapi/documentation-ui/).

###  Atlas (`/docs`)
sillo's own reference, and the default. Features:
- Three-pane layout with a request builder that sends real requests
- `⌘K` search that ranks results rather than filtering
- Code snippets in nine languages, generated from the request you built
- Light and dark, following the operating system
- Zero dependencies, styles inlined, one script tag

###  Swagger UI
Interactive interface for testing endpoints directly in the browser. Features:
- Live API testing with request/response examples
- Parameter input forms with validation
- Authentication support
- Response schema visualization

###  ReDoc (`/redoc`)
Clean, responsive documentation interface optimized for reading. Features:
- Three-column layout with navigation
- Code samples in multiple languages
- Detailed schema documentation
- Print-friendly format

###  Raw OpenAPI Specification (`/openapi.json`)
Machine-readable JSON specification for:
- Client SDK generation
- API testing tools
- Integration with other services
- Custom documentation tools

##  Basic Route Documentation
Every route automatically generates documentation including:
- HTTP method and path pattern
- Path parameters with type conversion
- Automatic response schema inference
- Default status codes and descriptions

```python
from sillo import HttpContext, json

@app.get("/health")
async def health_check(ctx: HttpContext):
    """Check if the API is running and responsive."""
    return json({
        "status": "healthy", 
        "timestamp": "2024-01-01T12:00:00Z"
    })
```

The docstring becomes the endpoint description, and sillo automatically documents the response structure.

##  Enhanced Documentation with Metadata

For production APIs, provide comprehensive metadata for professional documentation:

```python
from pydantic import BaseModel
from typing import Optional
from sillo import HttpContext

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    created_at: str

class ErrorResponse(BaseModel):
    error: str
    code: int
    details: Optional[dict] = None

@app.get(
    "/users/{user_id}",
    summary="Retrieve user profile",
    description="""
    Fetches detailed information for a specific user by their unique identifier.
    
    This endpoint returns comprehensive user data including profile information,
    account status, and metadata. The response includes both public and private
    fields depending on the requesting user's permissions.
    
    **Error Handling:**
    - Returns 404 if the user doesn't exist
    - Returns 403 if requesting user cannot access this profile
    - Returns 401 if authentication is required but not provided
    """,
    responses={
        200: UserResponse,
        404: ErrorResponse,
        403: ErrorResponse,
        401: ErrorResponse
    },
    tags=["Users", "Profiles"],
    operation_id="getUserById"
)
async def get_user_profile(ctx: HttpContext, user_id: int):
    """Retrieve a user's complete profile information."""
    # Implementation here
    pass
```

###  Documentation Components

**Summary**: A brief, one-line description that appears in endpoint lists. Keep it concise but descriptive.

**Description**: Detailed explanation of the endpoint's purpose, behavior, and important notes. Use markdown formatting for better readability.

**Tags**: Categorical labels that group related endpoints together in the documentation interface. This helps users navigate large APIs.

**Operation ID**: Unique identifier used for code generation and API client libraries.

**Responses**: Explicit response models for different status codes with proper error handling documentation.

##  Advanced Documentation Features

###  1. Multiple Response Types

sillo can document multiple possible responses for each endpoint:

```python
from pydantic import BaseModel
from typing import List, Union
from sillo import HttpContext

class User(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    created_at: str

class UserList(BaseModel):
    users: List[User]
    total: int
    page: int
    per_page: int

class ErrorResponse(BaseModel):
    error: str
    code: int
    details: dict = {}

@app.get(
    "/users",
    responses={
        200: UserList,
        400: ErrorResponse,
        401: ErrorResponse,
        500: ErrorResponse
    }
)
async def list_users(ctx: HttpContext):
    # Implementation
    pass

@app.get(
    "/users/{user_id}",
    responses={
        200: User,
        404: {"description": "User not found"},
        403: {"description": "Access denied"}
    }
)
async def get_user(ctx: HttpContext, user_id: int):
    # Implementation
    pass
```

###  2. Request Body Validation

Document and validate request bodies with Pydantic models:

```python
from sillo import HttpContext

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    is_active: bool = True

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None

@app.post(
    "/users",
    request_model=UserCreate,
    request_content_type="application/json",
    responses={
        201: User,
        400: ErrorResponse,
        409: {"description": "Username already exists"}
    }
)
async def create_user(ctx: HttpContext):
    # Access validated data via ctx.validated_data
    user_data = ctx.validated_data
    # Implementation
    pass

@app.patch(
    "/users/{user_id}",
    request_model=UserUpdate,
    responses={200: User, 404: ErrorResponse}
)
async def update_user(ctx: HttpContext, user_id: int):
    # Implementation
    pass
```

###  3. Parameter Documentation

Document path, query, and header parameters explicitly:

```python
from sillo.openapi.models import Query, Header
from sillo import HttpContext

@app.get(
    "/users",
    parameters=[
        Query(
            name="limit",
            description="Maximum number of users to return",
            required=False,
            schema={"type": "integer", "minimum": 1, "maximum": 100, "default": 20}
        ),
        Query(
            name="offset", 
            description="Number of users to skip for pagination",
            required=False,
            schema={"type": "integer", "minimum": 0, "default": 0}
        ),
        Header(
            name="X-Request-ID",
            description="Unique identifier for ctx tracking",
            required=False,
            schema={"type": "string", "format": "uuid"}
        )
    ]
)
async def list_users(ctx: HttpContext):
    limit = ctx.query_params.get('limit', 20)
    offset = ctx.query_params.get('offset', 0)
    # Implementation
    pass
```

###  4. Security Documentation

Document authentication and authorization requirements:

```python
from sillo import HttpContext

@app.get(
    "/users/me",
    security=[{"BearerAuth": []}],
    responses={
        200: User,
        401: {"description": "Authentication required"},
        403: {"description": "Invalid token"}
    }
)
async def get_current_user(ctx: HttpContext):
    # Implementation
    pass

@app.delete(
    "/users/{user_id}",
    security=[{"BearerAuth": ["admin"]}],
    responses={
        204: None,
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        404: {"description": "User not found"}
    }
)
async def delete_user(ctx: HttpContext, user_id: int):
    # Implementation
    pass
```

##  Organizing Large APIs

###  Using Tags for Grouping

Organize endpoints into logical groups using tags:

```python
# User management endpoints
from sillo import HttpContext

@app.get("/users", tags=["Users"])
async def list_users(ctx: HttpContext):
    pass

@app.post("/users", tags=["Users"])  
async def create_user(ctx: HttpContext):
    pass

# Authentication endpoints
@app.post("/auth/login", tags=["Authentication"])
async def login(ctx: HttpContext):
    pass

@app.post("/auth/logout", tags=["Authentication"])
async def logout(ctx: HttpContext):
    pass

# Admin-only endpoints
@app.get("/admin/stats", tags=["Admin", "Analytics"])
async def get_stats(ctx: HttpContext):
    pass
```

###  Router-Based Organization

Use routers to organize related endpoints with shared prefixes and tags:

```python
from sillo import HttpContext, Router

# User management router
users_router = Router(prefix="/users", tags=["Users"])

@users_router.get("/")
async def list_users(ctx: HttpContext):
    pass

@users_router.get("/{user_id}")
async def get_user(ctx: HttpContext, user_id: int):
    pass

@users_router.post("/")
async def create_user(ctx: HttpContext):
    pass

# Admin router with security
admin_router = Router(prefix="/admin", tags=["Admin"])

@admin_router.get("/users", security=[{"BearerAuth": ["admin"]}])
async def admin_list_users(ctx: HttpContext):
    pass

# Mount routers to main app
app.mount_router(users_router)
app.mount_router(admin_router)
```

##  Customizing OpenAPI Configuration

###  Application-Level Configuration

Configure OpenAPI metadata when creating your app:

```python
from sillo.openapi.models import Contact, License, Server

app = SilloApp(
    title="E-Commerce API",
    version="2.1.0",
    description="""
    A comprehensive e-commerce API providing:
    - Product catalog management
    - Order processing
    - User authentication
    - Payment integration
    """,
)

# Add additional servers
app.openapi_config.openapi_spec.servers = [
    Server(url="https://api.example.com", description="Production server"),
    Server(url="https://staging-api.example.com", description="Staging server"),
    Server(url="http://localhost:8000", description="Development server")
]

# Add contact information
app.openapi_config.openapi_spec.info.contact = Contact(
    name="API Support",
    url="https://example.com/support",
    email="api-support@example.com"
)

# Add license information
app.openapi_config.openapi_spec.info.license = License(
    name="MIT",
    url="https://opensource.org/licenses/MIT"
)
```

###  Custom Security Schemes

Define custom authentication schemes:

```python
from sillo.openapi.models import HTTPBearer, APIKey, OAuth2

# API Key authentication
app.openapi_config.add_security_scheme(
    "ApiKeyAuth",
    APIKey(type="apiKey", name="X-API-Key", in_="header")
)

# OAuth2 authentication
app.openapi_config.add_security_scheme(
    "OAuth2",
    OAuth2(
        type="oauth2",
        flows={
            "authorizationCode": {
                "authorizationUrl": "https://example.com/oauth/authorize",
                "tokenUrl": "https://example.com/oauth/token",
                "scopes": {
                    "read": "Read access",
                    "write": "Write access",
                    "admin": "Admin access"
                }
            }
        }
    )
)
```

###  Excluding Routes from Documentation

Hide internal or debug endpoints from public documentation:

```python
from sillo import HttpContext

@app.get("/internal/health", exclude_from_schema=True)
async def internal_health(ctx: HttpContext):
    """Internal health check - not shown in docs"""
    pass

@app.get("/debug/info", exclude_from_schema=True)
async def debug_info(ctx: HttpContext):
    """Debug endpoint - hidden from public API docs"""
    pass
```

##  Documentation Best Practices

###  Writing Effective Descriptions

**Be Specific and Actionable**:
```python
#  Vague
from sillo import HttpContext

@app.get("/users/{user_id}", summary="Get user")

#  Specific  
@app.get(
    "/users/{user_id}",
    summary="Retrieve user profile by ID",
    description="""
    Returns complete user profile including personal information, 
    account settings, and activity history. Requires authentication
    and appropriate permissions.
    
    **Rate Limits**: 100 requests per minute per user
    **Caching**: BaseResponse cached for 5 minutes
    """
)
async def handler(ctx: HttpContext): ...
```

**Document Error Conditions**:
```python
from sillo import HttpContext

@app.post(
    "/orders",
    description="""
    Creates a new order for the authenticated user.
    
    **Validation Rules**:
    - All items must be in stock
    - Total amount must be > $0
    - Payment method must be valid
    
    **Error Responses**:
    - 400: Invalid ctx data or validation errors
    - 401: Authentication required
    - 402: Payment method declined
    - 409: Items out of stock
    - 422: Business rule violations
    """,
    responses={
        201: OrderResponse,
        400: ValidationErrorResponse,
        401: {"description": "Authentication required"},
        402: {"description": "Payment declined"},
        409: {"description": "Items unavailable"},
        422: BusinessErrorResponse
    }
)
async def handler(ctx: HttpContext): ...
```

###  Consistent Naming Conventions

Use consistent patterns for operation IDs and route names:

```python
# Resource-based naming
from sillo import HttpContext

@app.get("/users", operation_id="listUsers", name="users-list")
@app.get("/users/{id}", operation_id="getUser", name="users-get")
@app.post("/users", operation_id="createUser", name="users-create")
@app.put("/users/{id}", operation_id="updateUser", name="users-update")
@app.delete("/users/{id}", operation_id="deleteUser", name="users-delete")
async def handler(ctx: HttpContext): ...
```

###  Deprecation Handling

Mark deprecated endpoints appropriately:

```python
from sillo import HttpContext

@app.get(
    "/api/v1/users",
    deprecated=True,
    description="""
    **DEPRECATED**: This endpoint is deprecated and will be removed in v3.0.
    Please use `/api/v2/users` instead.
    
    Migration guide: https://docs.example.com/migration/v1-to-v2
    """,
    tags=["Users (Deprecated)"]
)
async def list_users_v1(ctx: HttpContext):
    pass
```

##  Advanced Features

###  Custom Documentation URLs

Customize the documentation endpoint URLs:

```python
from sillo.openapi.ui import ReDoc, Swagger

app = SilloApp(
    openapi_url="/api-spec.json",
    docs=[
        Swagger(path="/api-docs"),
        ReDoc(path="/api-reference"),
    ],
)
```

The paths belong at construction. Routes are registered there, so assigning
`app.openapi.swagger_url` afterwards changes nothing. Passing `docs=[]` serves
no viewer at all. See [Documentation UI](/v1.0/guides/openapi/documentation-ui/).

###  Mounted Applications

When mounting sub-applications, each maintains its own documentation:

```python
# Main application
from sillo import HttpContext

main_app = SilloApp(title="Main API", version="1.0.0")

# Sub-application for admin features
admin_app = SilloApp(title="Admin API", version="1.0.0")

@admin_app.get("/users")
async def admin_list_users(ctx: HttpContext):
    pass

# Mount admin app - docs available at /admin/docs
main_app.register(admin_app, prefix="/admin")
```

###  Integration with Development Tools

The OpenAPI specification integrates with various development tools:

**Client Generation**:
```bash
# Generate TypeScript client
openapi-generator generate -i http://localhost:8000/openapi.json \
  -g typescript-axios -o ./client

# Generate Python client  
openapi-generator generate -i http://localhost:8000/openapi.json \
  -g python -o ./python-client
```

**API Testing**:
```bash
# Test with Postman
curl -o api-spec.json http://localhost:8000/openapi.json
# Import api-spec.json into Postman

# Test with Insomnia
# Import OpenAPI spec directly from URL
```

**Mock Servers**:
```bash
# Create mock server with Prism
prism mock http://localhost:8000/openapi.json
```

This comprehensive OpenAPI integration makes sillo ideal for API-first development, enabling teams to design, document, test, and consume APIs efficiently.

##  What a good OpenAPI document buys you

The document is not documentation with extra steps. It is a machine
contract, and four things consume it.

**Interactive docs.** Swagger UI and ReDoc render it directly, so an
integrator can read your API and call it in the same tab. This is the
visible benefit and the least valuable one.

**Client generation.** `openapi-generator` and its equivalents produce
typed clients for TypeScript, Swift, Kotlin, Go, and Python from the same
file. A team consuming your API writes no HTTP code and gets compile-time
errors when you break something.

**Contract testing.** Tools like Schemathesis read the schema and generate
requests that probe its edges: the boundary of every `maximum`, the empty
string on every `minLength`, unicode where you expected ASCII. It finds the
inputs you did not think to test, because it derives them from what you
published.

**Mock servers.** Prism and similar tools serve a fake implementation
from the document, so a frontend can be built before the backend exists,
against a shape that is guaranteed to match.

All four degrade in exact proportion to how accurate the document is,
which is the argument for generating it from the code that runs rather
than maintaining it beside.

##  Publishing the schema

The document lives at `/openapi.json` by default and the UIs at `/docs`
and `/redoc`. Three decisions to make before that reaches production.

**Whether to expose it publicly.** A public API should publish; an internal one
probably should not. The schema is a complete map of every endpoint, parameter,
and field name you have, including the endpoints you forgot were deployed. That
is a gift to anyone probing you.

**How to protect it if you keep it.** Put the docs routes behind the same
authentication as your admin, or restrict them by IP at the proxy.
Disabling them in production and generating a static copy for your own
teams is the option with the least surface.

**Which environment it describes.** A schema served from staging that
lists production URLs sends integrators to the wrong place. Set the
server URLs per environment rather than hard-coding one.

##  Keeping it honest as the API grows

Two failure modes appear once an API is more than a dozen routes.

**Untagged routes.** Without tags, the UI lists every endpoint in one flat
sequence and nobody can find anything. Tag from the first route, not when it
hurts, retrofitting tags across sixty endpoints is an afternoon nobody
schedules.

**Undocumented error responses.** Every endpoint documents its 200. Few
document the 404, the 409, or the 422 shape, and those are what an
integrator actually has to handle. A client written against a schema that
only describes success will handle failure by guessing.

Declare the error responses once, in a shared dict, and spread it into
every route so that consistency is the default rather than an act of
discipline.


##  Common failure modes

Four things that make a generated document less useful than it should be,
in rough order of frequency.

**Every route in one flat list.** No tags means no navigation. Fix it by
tagging from the first route.

**Only success responses documented.** Clients write the failure paths
too, and they need shapes for them.

**Operation summaries that repeat the path.** `GET /orders` summarised as "Get
orders" adds nothing. Say what it returns, what it excludes, and what it costs:
"List orders for the authenticated customer, newest first, excluding
cancelled".

**Models named after their internals.** `UserResponseModelV2` in a public
schema is a class name that escaped. Name published models the way you
would name them in a specification: `User`, `OrderSummary`,
`PaymentMethod`.
