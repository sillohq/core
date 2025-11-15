# OpenAPI Builder

The OpenAPI Builder in Nexios automatically generates comprehensive OpenAPI 3.0 documentation for your API, providing interactive documentation through Swagger UI and ReDoc interfaces.

## 📋 APIDocumentation Class

### Class Definition

```python
class APIDocumentation:
    def __init__(
        self,
        config: OpenAPIConfig,
        swagger_url: str = "/docs",
        redoc_url: str = "/redoc",
        openapi_url: str = "/openapi.json"
    )
```

The APIDocumentation class handles the generation and serving of OpenAPI documentation.

## ⚙️ OpenAPIConfig Class

::: tip Important
Always use proper Pydantic model instances (`Contact`, `License`, `Server`) instead of dictionaries when configuring OpenAPI. This ensures type safety and proper validation.
:::

### Configuration Options

```python
class OpenAPIConfig:
    def __init__(
        self,
        title: str = "Nexios API",
        version: str = "1.0.0",
        description: Optional[str] = None,
        servers: Optional[List[Server]] = None,
        contact: Optional[Contact] = None,
        license: Optional[License] = None,
        openapi_version: str = "3.0.0"
    )
```

### Basic Configuration

```python
from nexios.openapi.config import OpenAPIConfig
from nexios.openapi.models import Contact, License, Server

config = OpenAPIConfig(
    title="My API",
    version="2.0.0",
    description="A comprehensive API for managing users and resources",
    contact=Contact(
        name="API Support",
        url="https://example.com/contact",
        email="support@example.com"
    ),
    license=License(
        name="MIT",
        url="https://opensource.org/licenses/MIT"
    ),
    servers=[
        Server(url="https://api.example.com", description="Production server")
    ]
)

app = NexiosApp(config=MakeConfig({"openapi": config}))

# Alternative: Using MakeConfig with Pydantic models directly
app = NexiosApp(config=MakeConfig({
    "openapi": {
        "title": "My API",
        "version": "2.0.0", 
        "description": "A comprehensive API for managing users and resources",
        "contact": Contact(
            name="API Support",
            url="https://example.com/contact",
            email="support@example.com"
        ),
        "license": License(
            name="MIT",
            url="https://opensource.org/licenses/MIT"
        ),
        "servers": [
            Server(url="https://api.example.com", description="Production server")
        ]
    }
}))
```

### Advanced Configuration

```python
from nexios.openapi.models import Contact, License, Server, Tag, ExternalDocumentation

config = OpenAPIConfig(
    title="E-commerce API",
    version="3.1.0",
    description="""
    # E-commerce API
    
    This API provides comprehensive e-commerce functionality including:
    
    - User management and authentication
    - Product catalog management
    - Order processing and tracking
    - Payment integration
    - Inventory management
    
    ## Authentication
    
    This API uses JWT tokens for authentication. Include the token in the Authorization header:
    
    ```
    Authorization: Bearer <your-jwt-token>
    ```
    """,
    contact=Contact(
        name="E-commerce Team",
        url="https://example.com/support",
        email="api-support@example.com"
    ),
    license=License(
        name="Apache 2.0",
        url="https://www.apache.org/licenses/LICENSE-2.0.html"
    ),
    servers=[
        Server(url="https://api.example.com/v3", description="Production server"),
        Server(url="https://staging-api.example.com/v3", description="Staging server"),
        Server(url="http://localhost:8000", description="Development server")
    ]
)

# Add tags after creating the config
config.add_tag(Tag(
    name="Users",
    description="User management operations",
    externalDocs=ExternalDocumentation(
        description="User guide",
        url="https://docs.example.com/users"
    )
))

config.add_tag(Tag(
    name="Products",
    description="Product catalog operations"
))

config.add_tag(Tag(
    name="Orders", 
    description="Order management operations"
))

# Set external documentation
config.set_external_docs(ExternalDocumentation(
    description="Complete API Documentation",
    url="https://docs.example.com"
))
```

## 🔒 Security Schemes

### Adding Security Schemes

```python
from nexios.openapi.models import HTTPBearer, APIKey, OAuth2, OAuthFlows, OAuthFlowAuthorizationCode

# JWT Bearer Authentication
app.openapi_config.add_security_scheme(
    "BearerAuth",
    HTTPBearer(
        scheme="bearer",
        bearerFormat="JWT"
    )
)

# API Key Authentication  
app.openapi_config.add_security_scheme(
    "ApiKeyAuth",
    APIKey(
        name="X-API-Key",
        in_="header"
    )
)

# OAuth2 Authentication
oauth_flow = OAuthFlowAuthorizationCode(
    authorizationUrl="https://auth.example.com/oauth/authorize",
    tokenUrl="https://auth.example.com/oauth/token",
    scopes={
        "read": "Read access",
        "write": "Write access", 
        "admin": "Admin access"
    }
)

app.openapi_config.add_security_scheme(
    "OAuth2",
    OAuth2(
        flows=OAuthFlows(authorizationCode=oauth_flow)
    )
)
```

### Using Security in Routes

```python
@app.get(
    "/protected",
    security=[{"BearerAuth": []}],
    summary="Protected endpoint"
)
async def protected_endpoint(request: Request, response: Response):
    return response.json({"message": "This is a protected endpoint"})

@app.get(
    "/admin",
    security=[{"OAuth2": ["admin"]}],
    summary="Admin only endpoint"
)
async def admin_endpoint(request: Request, response: Response):
    return response.json({"message": "Admin access required"})
```

## 📖 Route Documentation

### Basic Route Documentation

```python
@app.get(
    "/users/{user_id}",
    summary="Get user by ID",
    description="Retrieve a specific user by their unique identifier",
    tags=["Users"]
)
async def get_user(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    user = await get_user_by_id(user_id)
    return response.json(user)
```

### Comprehensive Route Documentation

```python
from pydantic import BaseModel, Field
from typing import Optional

class UserResponse(BaseModel):
    id: int = Field(..., description="Unique user identifier")
    name: str = Field(..., description="User's full name")
    email: str = Field(..., description="User's email address")
    is_active: bool = Field(..., description="Whether the user account is active")
    created_at: str = Field(..., description="Account creation timestamp")

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    details: Optional[dict] = Field(None, description="Additional error details")

@app.get(
    "/users/{user_id}",
    summary="Get user by ID",
    description="""
    Retrieve a specific user by their unique identifier.
    
    This endpoint returns detailed user information including:
    - Basic profile information (name, email)
    - Account status and settings
    - Account creation timestamp
    
    **Note**: Only active users are returned. Deactivated accounts will return a 404 error.
    """,
    responses={
        200: {
            "description": "User found and returned successfully",
            "model": UserResponse
        },
        404: {
            "description": "User not found or account deactivated",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        403: {
            "description": "Insufficient permissions",
            "model": ErrorResponse
        }
    },
    tags=["Users"],
    security=[{"BearerAuth": []}],
    operation_id="getUserById",
    deprecated=False
)
async def get_user(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    
    # Authenticate user
    current_user = await authenticate_user(request)
    if not current_user:
        return response.status(401).json({
            "error": "Authentication required",
            "code": "AUTH_REQUIRED"
        })
    
    # Get user
    user = await get_user_by_id(user_id)
    if not user or not user.is_active:
        return response.status(404).json({
            "error": "User not found",
            "code": "USER_NOT_FOUND"
        })
    
    return response.json({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat()
    })
```

## 📄 Request/Response Models

### Request Body Models

```python
class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User's full name")
    email: str = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    age: Optional[int] = Field(None, ge=13, le=120, description="User's age")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "password": "securepassword123",
                "age": 30
            }
        }

@app.post(
    "/users",
    summary="Create new user",
    request_model=CreateUserRequest,
    responses={
        201: {"description": "User created successfully", "model": UserResponse},
        400: {"description": "Validation error", "model": ErrorResponse},
        409: {"description": "Email already exists", "model": ErrorResponse}
    }
)
async def create_user(request: Request, response: Response):
    try:
        json_data = await request.json
        user_data = CreateUserRequest(**json_data)
        
        # Create user
        user = await create_user_service(user_data)
        return response.status(201).json(user)
        
    except ValidationError as e:
        return response.status(400).json({
            "error": "Validation failed",
            "code": "VALIDATION_ERROR",
            "details": e.errors()
        })
```

### Query Parameter Models

```python
class UserListQuery(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(20, ge=1, le=100, description="Items per page")
    search: Optional[str] = Field(None, description="Search term for name or email")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    sort_by: Optional[str] = Field("created_at", description="Sort field")
    sort_order: Optional[str] = Field("desc", regex="^(asc|desc)$", description="Sort order")

@app.get(
    "/users",
    summary="List users",
    request_model=UserListQuery,
    responses={
        200: {
            "description": "Users retrieved successfully",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "users": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/UserResponse"}
                            },
                            "pagination": {
                                "type": "object",
                                "properties": {
                                    "page": {"type": "integer"},
                                    "limit": {"type": "integer"},
                                    "total": {"type": "integer"},
                                    "pages": {"type": "integer"}
                                }
                            }
                        }
                    }
                }
            }
        }
    }
)
async def list_users(request: Request, response: Response):
    # Parse query parameters
    query_params = UserListQuery(**dict(request.query_params))
    
    # Get users with pagination
    users, total = await get_users_paginated(
        page=query_params.page,
        limit=query_params.limit,
        search=query_params.search,
        is_active=query_params.is_active,
        sort_by=query_params.sort_by,
        sort_order=query_params.sort_order
    )
    
    return response.json({
        "users": users,
        "pagination": {
            "page": query_params.page,
            "limit": query_params.limit,
            "total": total,
            "pages": (total + query_params.limit - 1) // query_params.limit
        }
    })
```

## 🔧 Custom Parameters

### Path Parameters

```python
from nexios.openapi.models import Path, Schema

@app.get(
    "/users/{user_id}/posts/{post_id}",
    summary="Get user post",
    parameters=[
        Path(
            name="user_id",
            schema=Schema(type="integer", minimum=1),
            description="Unique user identifier"
        ),
        Path(
            name="post_id", 
            schema=Schema(type="integer", minimum=1),
            description="Unique post identifier"
        )
    ]
)
async def get_user_post(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    post_id = request.path_params["post_id"]
    
    post = await get_post(user_id, post_id)
    return response.json(post)
```

### Header Parameters

```python
from nexios.openapi.models import Header, Schema

@app.get(
    "/data",
    summary="Get data with custom headers",
    parameters=[
        Header(
            name="X-Client-Version",
            required=False,
            schema=Schema(type="string"),
            description="Client application version"
        ),
        Header(
            name="Accept-Language",
            required=False,
            schema=Schema(type="string", default="en"),
            description="Preferred language for response"
        )
    ]
)
async def get_data(request: Request, response: Response):
    client_version = request.headers.get("X-Client-Version")
    language = request.headers.get("Accept-Language", "en")
    
    data = await get_localized_data(language, client_version)
    return response.json(data)
```

## 📝 Custom Documentation

### Adding Custom Schemas

```python
from nexios.openapi.models import Schema

# Add custom schema to OpenAPI using Schema model
pagination_schema = Schema(
    type="object",
    properties={
        "page": Schema(type="integer", description="Current page number"),
        "limit": Schema(type="integer", description="Items per page"),
        "total": Schema(type="integer", description="Total number of items"),
        "pages": Schema(type="integer", description="Total number of pages")
    },
    required=["page", "limit", "total", "pages"]
)

app.openapi_config.add_schema("PaginationInfo", pagination_schema)

# Reference custom schema in responses
@app.get(
    "/items",
    responses={
        200: {
            "description": "Items retrieved successfully",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {"type": "object"}
                            },
                            "pagination": {"$ref": "#/components/schemas/PaginationInfo"}
                        }
                    }
                }
            }
        }
    }
)
async def list_items(request: Request, response: Response):
    # Implementation
    pass
```

### Custom Response Examples

```python
@app.post(
    "/users",
    summary="Create user",
    responses={
        201: {
            "description": "User created successfully",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/UserResponse"},
                    "examples": {
                        "successful_creation": {
                            "summary": "Successful user creation",
                            "description": "Example of a successful user creation response",
                            "value": {
                                "id": 123,
                                "name": "John Doe",
                                "email": "john.doe@example.com",
                                "is_active": True,
                                "created_at": "2023-01-01T12:00:00Z"
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "examples": {
                        "validation_error": {
                            "summary": "Validation error example",
                            "value": {
                                "error": "Validation failed",
                                "code": "VALIDATION_ERROR",
                                "details": [
                                    {
                                        "field": "email",
                                        "message": "Invalid email format"
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        }
    }
)
async def create_user(request: Request, response: Response):
    # Implementation
    pass
```

## 🎨 Customizing Documentation UI

### Swagger UI Customization

```python
from nexios.openapi._builder import APIDocumentation

class CustomAPIDocumentation(APIDocumentation):
    def _generate_swagger_ui(self, openapi_url: str) -> str:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>My API Documentation</title>
            <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@3.52.5/swagger-ui.css" />
            <style>
                .swagger-ui .topbar {{ display: none; }}
                .swagger-ui .info .title {{ color: #3b82f6; }}
            </style>
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@3.52.5/swagger-ui-bundle.js"></script>
            <script>
                SwaggerUIBundle({{
                    url: '{openapi_url}',
                    dom_id: '#swagger-ui',
                    presets: [
                        SwaggerUIBundle.presets.apis,
                        SwaggerUIBundle.presets.standalone
                    ],
                    layout: "BaseLayout",
                    deepLinking: true,
                    showExtensions: true,
                    showCommonExtensions: true,
                    defaultModelsExpandDepth: 2,
                    defaultModelExpandDepth: 2
                }});
            </script>
        </body>
        </html>
        """

# Use custom documentation
app.openapi = CustomAPIDocumentation(
    config=app.openapi_config,
    swagger_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)
```

### ReDoc Customization

```python
class CustomAPIDocumentation(APIDocumentation):
    def _generate_redoc_ui(self, openapi_url: str) -> str:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>My API Documentation - ReDoc</title>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
            <style>
                body {{ margin: 0; padding: 0; }}
            </style>
        </head>
        <body>
            <redoc spec-url='{openapi_url}' theme='{{
                "colors": {{
                    "primary": {{
                        "main": "#3b82f6"
                    }}
                }}
            }}'></redoc>
            <script src="https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js"></script>
        </body>
        </html>
        """
```

## 🚫 Excluding Routes from Documentation

### Exclude Individual Routes

```python
@app.get("/internal", exclude_from_schema=True)
async def internal_endpoint(request: Request, response: Response):
    return response.json({"message": "This won't appear in OpenAPI docs"})
```

### Exclude Router

```python
internal_router = Router(prefix="/internal")

@internal_router.get("/health")
async def internal_health(request: Request, response: Response):
    return response.json({"status": "ok"})

# Mount router but exclude from schema
app.mount_router(internal_router, exclude_from_schema=True)
```

## 🏗️ Generating OpenAPI Specification

### Programmatic Access

```python
# Get OpenAPI specification as dictionary
openapi_spec = app.openapi.get_openapi(app.router)

# Save to file
import json
with open("openapi.json", "w") as f:
    json.dump(openapi_spec, f, indent=2)

# Generate YAML
import yaml
with open("openapi.yaml", "w") as f:
    yaml.dump(openapi_spec, f, default_flow_style=False)
```

### CLI Generation

```python
# Create CLI command for generating OpenAPI spec
import click

@click.command()
@click.option("--output", "-o", default="openapi.json", help="Output file")
@click.option("--format", "-f", type=click.Choice(["json", "yaml"]), default="json")
def generate_openapi(output: str, format: str):
    """Generate OpenAPI specification file"""
    from myapp import app
    
    spec = app.openapi.get_openapi(app.router)
    
    if format == "yaml":
        import yaml
        with open(output, "w") as f:
            yaml.dump(spec, f, default_flow_style=False)
    else:
        import json
        with open(output, "w") as f:
            json.dump(spec, f, indent=2)
    
    click.echo(f"OpenAPI specification saved to {output}")

if __name__ == "__main__":
    generate_openapi()
```

## ✨ Best Practices

1. **Provide comprehensive descriptions** for all endpoints
2. **Use proper HTTP status codes** and document all possible responses
3. **Include request/response examples** for better understanding
4. **Use consistent naming conventions** for operations and schemas
5. **Group related endpoints** using tags
6. **Document authentication requirements** clearly
7. **Include validation rules** in parameter descriptions
8. **Use semantic versioning** for API versions
9. **Provide contact information** for API support
10. **Keep documentation up to date** with code changes

## 🚀 Advanced Features

### Custom OpenAPI Extensions

```python
# Add custom extensions to OpenAPI spec
@app.get(
    "/users",
    summary="List users",
    **{
        "x-code-samples": [
            {
                "lang": "Python",
                "source": """
import requests

response = requests.get('https://api.example.com/users')
users = response.json()
                """
            },
            {
                "lang": "JavaScript",
                "source": """
fetch('https://api.example.com/users')
  .then(response => response.json())
  .then(users => console.log(users));
                """
            }
        ],
        "x-rate-limit": {
            "limit": 100,
            "window": "1h"
        }
    }
)
async def list_users(request: Request, response: Response):
    # Implementation
    pass
```

### Webhook Documentation

```python
# Document webhooks in OpenAPI
app.openapi_config.add_webhook("user_created", {
    "post": {
        "summary": "User Created Webhook",
        "description": "Triggered when a new user is created",
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "event": {"type": "string", "example": "user.created"},
                            "data": {"$ref": "#/components/schemas/UserResponse"},
                            "timestamp": {"type": "string", "format": "date-time"}
                        }
                    }
                }
            }
        },
        "responses": {
            "200": {"description": "Webhook received successfully"}
        }
    }
})
```

## 🔍 See Also

- [OpenAPI Models](./models.md) - OpenAPI model definitions
- [OpenAPI Configuration](./config.md) - Configuration options
- [Application](../application/nexios-app.md) - Application setup
- [Router](../routing/router.md) - Route documentation
- [Authentication](../auth/base.md) - Security documentation