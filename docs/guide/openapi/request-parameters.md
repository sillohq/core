# 📝 Request Parameters in Nexios

Request parameters make your API flexible, searchable, and powerful. Nexios supports comprehensive parameter documentation for path parameters, query parameters, headers, and cookies. This guide shows how to document each type effectively in your OpenAPI specification.

> **Important**: Always use specific parameter types (`Path`, `Query`, `Header`, `Cookie`) instead of the generic `Parameter` type. This ensures proper OpenAPI specification generation and better type safety.

## 📦 Imports

Before using request parameters, import the specific parameter types you need:

```python
from nexios.openapi.models import Path, Query, Header, Cookie
```

## 🎯 Types of Request Parameters

Nexios supports four main parameter types:

- **Path Parameters**: Part of the URL path (e.g., `/users/{user_id}`) - use `Path`
- **Query Parameters**: URL query string parameters (e.g., `?limit=10&page=2`) - use `Query`
- **Header Parameters**: HTTP headers (e.g., `Authorization`, `X-API-Key`) - use `Header`
- **Cookie Parameters**: HTTP cookies (e.g., `session_id`) - use `Cookie`

## 🛣️ Path Parameters

Path parameters are automatically detected and documented by Nexios when you use parameter syntax in your route paths:

```python
from nexios import NexiosApp
from nexios.openapi.models import Path, Query, Header, Cookie
from typing import Optional

app = NexiosApp()

@app.get(
    "/users/{user_id}",
    summary="Get user by ID",
    description="Retrieves a specific user by their unique identifier"
)
async def get_user(request, response, user_id: int):
    """Fetch a user by their unique ID."""
    return response.json({"user_id": user_id, "name": "John Doe"})

@app.get("/posts/{post_id}/comments/{comment_id}")
async def get_comment(request, response, post_id: int, comment_id: int):
    """Get a specific comment from a specific post."""
    return response.json({
        "post_id": post_id,
        "comment_id": comment_id,
        "content": "Great post!"
    })

# Path parameters with type constraints
@app.get("/files/{file_path:path}")
async def get_file(request, response, file_path: str):
    """Get file by path (supports nested paths with slashes)."""
    return response.json({"file_path": file_path})

@app.get("/products/{product_id:int}")
async def get_product(request, response, product_id: int):
    """Get product by integer ID."""
    return response.json({"product_id": product_id})
```

### Path Parameter Types

Nexios supports several path parameter types:

```python
# String parameter (default)
@app.get("/users/{username}")
async def get_user_by_name(request, response, username: str):
    pass

# Integer parameter
@app.get("/users/{user_id:int}")
async def get_user_by_id(request, response, user_id: int):
    pass

# Float parameter
@app.get("/prices/{price:float}")
async def get_by_price(request, response, price: float):
    pass

# Path parameter (captures slashes)
@app.get("/files/{file_path:path}")
async def get_file_by_path(request, response, file_path: str):
    pass
```

## ❓ Query Parameters

Query parameters provide filtering, sorting, pagination, and search capabilities. Document them explicitly using the `parameters` argument:

```python
from nexios.openapi.models import Query

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
        Query(
            name="search",
            description="Search term to filter users by name or email",
            required=False,
            schema={"type": "string", "minLength": 2}
        ),
        Query(
            name="status",
            description="Filter users by account status",
            required=False,
            schema={
                "type": "string",
                "enum": ["active", "inactive", "suspended"],
                "default": "active"
            }
        ),
        Query(
            name="sort_by",
            description="Field to sort users by",
            required=False,
            schema={
                "type": "string",
                "enum": ["name", "email", "created_at", "last_login"],
                "default": "created_at"
            }
        ),
        Query(
            name="sort_order",
            description="Sort order for results",
            required=False,
            schema={
                "type": "string",
                "enum": ["asc", "desc"],
                "default": "desc"
            }
        )
    ],
    summary="List users with filtering and pagination"
)
async def list_users(request, response):
    # Extract query parameters
    limit = int(request.query_params.get('limit', 20))
    offset = int(request.query_params.get('offset', 0))
    search = request.query_params.get('search')
    status = request.query_params.get('status', 'active')
    sort_by = request.query_params.get('sort_by', 'created_at')
    sort_order = request.query_params.get('sort_order', 'desc')
    
    # Apply filters and return results
    return response.json({
        "users": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "filters": {
            "search": search,
            "status": status,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
    })
```

### Advanced Query Parameter Patterns

```python
# Array parameters
@app.get(
    "/products",
    parameters=[
        Query(
            name="categories",
            description="Filter by multiple categories",
            required=False,
            schema={
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 10
            },
            style="form",
            explode=True  # ?categories=electronics&categories=books
        ),
        Query(
            name="price_range",
            description="Price range filter (min,max)",
            required=False,
            schema={
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2
            },
            style="form",
            explode=False  # ?price_range=10,100
        )
    ]
)
async def list_products(request, response):
    categories = request.query_params.getlist('categories')
    price_range = request.query_params.get('price_range', '').split(',')
    
    return response.json({
        "products": [],
        "filters": {
            "categories": categories,
            "price_range": price_range
        }
    })

# Boolean parameters
@app.get(
    "/articles",
    parameters=[
        Query(
            name="published",
            description="Filter by publication status",
            required=False,
            schema={
                "type": "boolean",
                "default": True
            }
        ),
        Query(
            name="featured",
            description="Show only featured articles",
            required=False,
            schema={"type": "boolean"}
        )
    ]
)
async def list_articles(request, response):
    published = request.query_params.get('published', 'true').lower() == 'true'
    featured = request.query_params.get('featured', '').lower() == 'true'
    
    return response.json({
        "articles": [],
        "filters": {"published": published, "featured": featured}
    })
```

## 📋 Header Parameters

Headers are used for authentication, content negotiation, client information, and custom metadata:

```python
from nexios.openapi.models import Header

@app.get(
    "/users/me",
    parameters=[
        Header(
            name="Authorization",
            description="Bearer token for authentication",
            required=True,
            schema={"type": "string", "pattern": "^Bearer .+"}
        ),
        Header(
            name="X-Request-ID",
            description="Unique identifier for request tracing",
            required=False,
            schema={"type": "string", "format": "uuid"}
        ),
        Header(
            name="Accept-Language",
            description="Preferred language for response",
            required=False,
            schema={
                "type": "string",
                "enum": ["en", "es", "fr", "de"],
                "default": "en"
            }
        ),
        Header(
            name="X-Client-Version",
            description="Client application version",
            required=False,
            schema={"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"}
        )
    ],
    summary="Get current user profile"
)
async def get_current_user(request, response):
    # Extract headers
    auth_header = request.headers.get('Authorization')
    request_id = request.headers.get('X-Request-ID')
    language = request.headers.get('Accept-Language', 'en')
    client_version = request.headers.get('X-Client-Version')
    
    return response.json({
        "user": {"id": 123, "username": "current_user"},
        "request_id": request_id,
        "language": language,
        "client_version": client_version
    })
```

## 🍪 Cookie Parameters

Cookie parameters are used for session management, user preferences, and tracking:

```python
from nexios.openapi.models import Cookie

@app.get(
    "/dashboard",
    parameters=[
        Cookie(
            name="session_id",
            description="User session identifier",
            required=True,
            schema={"type": "string", "format": "uuid"}
        ),
        Cookie(
            name="theme",
            description="User interface theme preference",
            required=False,
            schema={
                "type": "string",
                "enum": ["light", "dark", "auto"],
                "default": "auto"
            }
        ),
        Cookie(
            name="timezone",
            description="User timezone for date/time display",
            required=False,
            schema={"type": "string", "default": "UTC"}
        )
    ],
    summary="Get user dashboard"
)
async def get_dashboard(request, response):
    # Extract cookies
    session_id = request.cookies.get('session_id')
    theme = request.cookies.get('theme', 'auto')
    timezone = request.cookies.get('timezone', 'UTC')
    
    if not session_id:
        return response.json({
            "error": "Session required"
        }, status=401)
    
    return response.json({
        "dashboard": {"widgets": []},
        "preferences": {
            "theme": theme,
            "timezone": timezone
        }
    })
```


### Complex Parameter Schemas

```python
@app.get(
    "/analytics/reports",
    parameters=[
        Query(
            name="date_range",
            description="Date range for the report",
            required=True,
            schema={
                "type": "string",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}:\\d{4}-\\d{2}-\\d{2}$",
                "example": "2024-01-01:2024-01-31"
            }
        ),
        Query(
            name="metrics",
            description="Metrics to include in the report",
            required=True,
            schema={
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["views", "clicks", "conversions", "revenue"]
                },
                "minItems": 1,
                "maxItems": 4,
                "uniqueItems": True
            },
            style="form",
            explode=True
        ),
        Query(
            name="granularity",
            description="Data granularity",
            required=False,
            schema={
                "type": "string",
                "enum": ["hour", "day", "week", "month"],
                "default": "day"
            }
        )
    ]
)
async def get_analytics_report(request, response):
    date_range = request.query_params.get('date_range')
    metrics = request.query_params.getlist('metrics')
    granularity = request.query_params.get('granularity', 'day')
    
    # Validate date range format
    try:
        start_date, end_date = date_range.split(':')
        # Additional validation logic
    except ValueError:
        return response.json({
            "error": "Invalid date range format. Use YYYY-MM-DD:YYYY-MM-DD"
        }, status=400)
    
    return response.json({
        "report": {
            "date_range": {"start": start_date, "end": end_date},
            "metrics": metrics,
            "granularity": granularity,
            "data": []
        }
    })
```

### Parameter Dependencies

Document parameters that depend on each other:

```python
@app.get(
    "/search",
    parameters=[
        Query(
            name="q",
            description="Search query",
            required=False,
            schema={"type": "string", "minLength": 2}
        ),
        Query(
            name="category",
            description="Search within specific category",
            required=False,
            schema={
                "type": "string",
                "enum": ["products", "articles", "users"]
            }
        ),
        Query(
            name="advanced",
            description="Enable advanced search (requires 'q' parameter)",
            required=False,
            schema={"type": "boolean", "default": False}
        )
    ],
    description="""
    Search endpoint with parameter dependencies:
    - Either 'q' or 'category' must be provided
    - 'advanced' can only be used with 'q'
    """
)
async def search(request, response):
    query = request.query_params.get('q')
    category = request.query_params.get('category')
    advanced = request.query_params.get('advanced', 'false').lower() == 'true'
    
    if not query and not category:
        return response.json({
            "error": "Either 'q' or 'category' parameter is required"
        }, status=400)
    
    if advanced and not query:
        return response.json({
            "error": "Advanced search requires 'q' parameter"
        }, status=400)
    
    return response.json({
        "results": [],
        "query": query,
        "category": category,
        "advanced": advanced
    })
```

## ✅ Best Practices

### Parameter Naming Conventions

```python
# Use consistent naming patterns
@app.get("/users", parameters=[
    Query(name="user_id"),                       # snake_case for multi-word
    Query(name="limit"),                         # lowercase for single word
    Query(name="sort_by"),                       # descriptive names
    Header(name="X-API-Key"),                    # X- prefix for custom headers
])

# Avoid ambiguous names
# ❌ Bad
Query(name="id")                               # Which ID?
Query(name="type")                             # Type of what?

# ✅ Good  
Query(name="user_id")                          # Clear and specific
Query(name="content_type")                     # Descriptive
```

### Parameter Documentation

```python
@app.get(
    "/orders",
    parameters=[
        Query(
            name="status",
            description="Filter orders by status. Use 'pending' for new orders, 'processing' for orders being fulfilled, 'shipped' for dispatched orders, and 'delivered' for completed orders.",
            required=False,
            schema={
                "type": "string",
                "enum": ["pending", "processing", "shipped", "delivered"],
                "default": "pending"
            }
        )
    ]
)
```

### Parameter Validation

```python
def validate_date_range(date_range: str) -> bool:
    """Validate date range parameter format"""
    try:
        start, end = date_range.split(':')
        # Additional validation logic
        return True
    except ValueError:
        return False

@app.get("/reports")
async def get_reports(request, response):
    date_range = request.query_params.get('date_range')
    
    if date_range and not validate_date_range(date_range):
        return response.json({
            "error": "Invalid date range format"
        }, status=400)
```

Request parameters are essential for creating flexible, powerful APIs. Proper documentation ensures that API consumers understand how to use your endpoints effectively and helps prevent integration issues.
