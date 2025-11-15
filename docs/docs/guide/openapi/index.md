# 📋 OpenAPI Documentation in Nexios

Nexios provides comprehensive, automatic API documentation powered by the OpenAPI 3.0 standard. Every route you define is automatically documented with interactive UIs, type validation, and professional-grade specifications.

## 🚀 Quick Start

By default, Nexios generates complete OpenAPI documentation for all your routes:

```python
from nexios import NexiosApp

app = NexiosApp(
    title="My API",
    version="1.0.0", 
    description="A comprehensive API built with Nexios"
)

@app.get("/users/{user_id}")
async def get_user(request, response, user_id: int):
    """Retrieve a user by their ID."""
    return response.json({"id": user_id, "name": "John Doe"})
```

This automatically creates:
- **Interactive Swagger UI** at `/docs`
- **ReDoc documentation** at `/redoc` 
- **OpenAPI JSON specification** at `/openapi.json`

## 📖 Documentation Interfaces

Nexios provides multiple ways to explore your API:

### Swagger UI (`/docs`)
Interactive interface for testing endpoints directly in the browser. Features:
- Live API testing with request/response examples
- Parameter input forms with validation
- Authentication support
- Response schema visualization

### ReDoc (`/redoc`)
Clean, responsive documentation interface optimized for reading. Features:
- Three-column layout with navigation
- Code samples in multiple languages
- Detailed schema documentation
- Print-friendly format

### Raw OpenAPI Specification (`/openapi.json`)
Machine-readable JSON specification for:
- Client SDK generation
- API testing tools
- Integration with other services
- Custom documentation tools

## 🎯 Basic Route Documentation
Every route automatically generates documentation including:
- HTTP method and path pattern
- Path parameters with type conversion
- Automatic response schema inference
- Default status codes and descriptions

```python
@app.get("/health")
async def health_check(request, response):
    """Check if the API is running and responsive."""
    return response.json({
        "status": "healthy", 
        "timestamp": "2024-01-01T12:00:00Z"
    })
```

The docstring becomes the endpoint description, and Nexios automatically documents the response structure.

## 🔧 Enhanced Documentation with Metadata

For production APIs, provide comprehensive metadata for professional documentation:

```python
from pydantic import BaseModel
from typing import Optional

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
async def get_user_profile(request, response, user_id: int):
    """Retrieve a user's complete profile information."""
    # Implementation here
    pass
```

### Documentation Components

**Summary**: A brief, one-line description that appears in endpoint lists. Keep it concise but descriptive.

**Description**: Detailed explanation of the endpoint's purpose, behavior, and important notes. Use markdown formatting for better readability.

**Tags**: Categorical labels that group related endpoints together in the documentation interface. This helps users navigate large APIs.

**Operation ID**: Unique identifier used for code generation and API client libraries.

**Responses**: Explicit response models for different status codes with proper error handling documentation.

## 🎨 Advanced Documentation Features

### 1. Multiple Response Types

Nexios can document multiple possible responses for each endpoint:

```python
from pydantic import BaseModel
from typing import List, Union

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
async def list_users(request, response):
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
async def get_user(request, response, user_id: int):
    # Implementation
    pass
```

### 2. Request Body Validation

Document and validate request bodies with Pydantic models:

```python
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
async def create_user(request, response):
    # Access validated data via request.validated_data
    user_data = request.validated_data
    # Implementation
    pass

@app.patch(
    "/users/{user_id}",
    request_model=UserUpdate,
    responses={200: User, 404: ErrorResponse}
)
async def update_user(request, response, user_id: int):
    # Implementation
    pass
```

### 3. Parameter Documentation

Document path, query, and header parameters explicitly:

```python
from nexios.openapi.models import Query, Header

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
            description="Unique identifier for request tracking",
            required=False,
            schema={"type": "string", "format": "uuid"}
        )
    ]
)
async def list_users(request, response):
    limit = request.query_params.get('limit', 20)
    offset = request.query_params.get('offset', 0)
    # Implementation
    pass
```

### 4. Security Documentation

Document authentication and authorization requirements:

```python
@app.get(
    "/users/me",
    security=[{"BearerAuth": []}],
    responses={
        200: User,
        401: {"description": "Authentication required"},
        403: {"description": "Invalid token"}
    }
)
async def get_current_user(request, response):
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
async def delete_user(request, response, user_id: int):
    # Implementation
    pass
```

## 🏗️ Organizing Large APIs

### Using Tags for Grouping

Organize endpoints into logical groups using tags:

```python
# User management endpoints
@app.get("/users", tags=["Users"])
async def list_users(request, response):
    pass

@app.post("/users", tags=["Users"])  
async def create_user(request, response):
    pass

# Authentication endpoints
@app.post("/auth/login", tags=["Authentication"])
async def login(request, response):
    pass

@app.post("/auth/logout", tags=["Authentication"])
async def logout(request, response):
    pass

# Admin-only endpoints
@app.get("/admin/stats", tags=["Admin", "Analytics"])
async def get_stats(request, response):
    pass
```

### Router-Based Organization

Use routers to organize related endpoints with shared prefixes and tags:

```python
from nexios import Router

# User management router
users_router = Router(prefix="/users", tags=["Users"])

@users_router.get("/")
async def list_users(request, response):
    pass

@users_router.get("/{user_id}")
async def get_user(request, response, user_id: int):
    pass

@users_router.post("/")
async def create_user(request, response):
    pass

# Admin router with security
admin_router = Router(prefix="/admin", tags=["Admin"])

@admin_router.get("/users", security=[{"BearerAuth": ["admin"]}])
async def admin_list_users(request, response):
    pass

# Mount routers to main app
app.mount_router(users_router)
app.mount_router(admin_router)
```

## ⚙️ Customizing OpenAPI Configuration

### Application-Level Configuration

Configure OpenAPI metadata when creating your app:

```python
from nexios.openapi.models import Contact, License, Server

app = NexiosApp(
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

### Custom Security Schemes

Define custom authentication schemes:

```python
from nexios.openapi.models import HTTPBearer, APIKey, OAuth2

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

### Excluding Routes from Documentation

Hide internal or debug endpoints from public documentation:

```python
@app.get("/internal/health", exclude_from_schema=True)
async def internal_health(request, response):
    """Internal health check - not shown in docs"""
    pass

@app.get("/debug/info", exclude_from_schema=True)
async def debug_info(request, response):
    """Debug endpoint - hidden from public API docs"""
    pass
```

## 📝 Documentation Best Practices

### Writing Effective Descriptions

**Be Specific and Actionable**:
```python
# ❌ Vague
@app.get("/users/{user_id}", summary="Get user")

# ✅ Specific  
@app.get(
    "/users/{user_id}",
    summary="Retrieve user profile by ID",
    description="""
    Returns complete user profile including personal information, 
    account settings, and activity history. Requires authentication
    and appropriate permissions.
    
    **Rate Limits**: 100 requests per minute per user
    **Caching**: Response cached for 5 minutes
    """
)
```

**Document Error Conditions**:
```python
@app.post(
    "/orders",
    description="""
    Creates a new order for the authenticated user.
    
    **Validation Rules**:
    - All items must be in stock
    - Total amount must be > $0
    - Payment method must be valid
    
    **Error Responses**:
    - 400: Invalid request data or validation errors
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
```

### Consistent Naming Conventions

Use consistent patterns for operation IDs and route names:

```python
# Resource-based naming
@app.get("/users", operation_id="listUsers", name="users-list")
@app.get("/users/{id}", operation_id="getUser", name="users-get")
@app.post("/users", operation_id="createUser", name="users-create")
@app.put("/users/{id}", operation_id="updateUser", name="users-update")
@app.delete("/users/{id}", operation_id="deleteUser", name="users-delete")
```

### Deprecation Handling

Mark deprecated endpoints appropriately:

```python
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
async def list_users_v1(request, response):
    pass
```

## 🔧 Advanced Features

### Custom Documentation URLs

Customize the documentation endpoint URLs:

```python
app = NexiosApp()

# Custom URLs for documentation
app.openapi.swagger_url = "/api-docs"
app.openapi.redoc_url = "/api-reference" 
app.openapi.openapi_url = "/api-spec.json"
```

### Mounted Applications

When mounting sub-applications, each maintains its own documentation:

```python
# Main application
main_app = NexiosApp(title="Main API", version="1.0.0")

# Sub-application for admin features
admin_app = NexiosApp(title="Admin API", version="1.0.0")

@admin_app.get("/users")
async def admin_list_users(request, response):
    pass

# Mount admin app - docs available at /admin/docs
main_app.register(admin_app, prefix="/admin")
```

### Integration with Development Tools

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

This comprehensive OpenAPI integration makes Nexios ideal for API-first development, enabling teams to design, document, test, and consume APIs efficiently.