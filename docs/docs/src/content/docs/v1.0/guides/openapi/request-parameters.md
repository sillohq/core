---
title: Request Parameters in sillo
description: >
    Request parameters make your API flexible, searchable, and powerful. sillo supports comprehensive parameter documentation for path parameters, query parameters, headers, and cookies in your OpenAPI specification.
---

#  Request Parameters in sillo

Request parameters make your API flexible, searchable, and powerful. sillo supports comprehensive parameter documentation for path parameters, query parameters, headers, and cookies. This guide shows how to document each type effectively in your OpenAPI specification.

> **Important**: Always use specific parameter types (`Path`, `Query`, `Header`, `Cookie`) instead of the generic `Parameter` type. This ensures proper OpenAPI specification generation and better type safety.

##  Imports

Before using request parameters, import the specific parameter types you need:

```python
from sillo.openapi.models import Path, Query, Header, Cookie
```

##  Types of Request Parameters

sillo supports four main parameter types:

- **Path Parameters**: Part of the URL path (e.g., `/users/{user_id}`) - use `Path`
- **Query Parameters**: URL query string parameters (e.g., `?limit=10&page=2`) - use `Query`
- **Header Parameters**: HTTP headers (e.g., `Authorization`, `X-API-Key`) - use `Header`
- **Cookie Parameters**: HTTP cookies (e.g., `session_id`) - use `Cookie`

##  Path Parameters

Path parameters are automatically detected and documented by sillo when you use parameter syntax in your route paths:

```python
from sillo import SilloApp, HttpContext
from sillo.openapi.models import Path, Query, Header, Cookie
from typing import Optional

app = SilloApp()

@app.get(
    "/users/{user_id}",
    summary="Get user by ID",
    description="Retrieves a specific user by their unique identifier"
)
async def get_user(ctx: HttpContext, user_id: int):
    """Fetch a user by their unique ID."""
    return {"user_id": user_id, "name": "John Doe"}

@app.get("/posts/{post_id}/comments/{comment_id}")
async def get_comment(ctx: HttpContext, post_id: int, comment_id: int):
    """Get a specific comment from a specific post."""
    return {
        "post_id": post_id,
        "comment_id": comment_id,
        "content": "Great post!"
    }

# Path parameters with type constraints
@app.get("/files/{file_path:path}")
async def get_file(ctx: HttpContext, file_path: str):
    """Get file by path (supports nested paths with slashes)."""
    return {"file_path": file_path}

@app.get("/products/{product_id:int}")
async def get_product(ctx: HttpContext, product_id: int):
    """Get product by integer ID."""
    return {"product_id": product_id}
```

###  Path Parameter Types

sillo supports several path parameter types:

```python
# String parameter (default)
from sillo import HttpContext

@app.get("/users/{username}")
async def get_user_by_name(ctx: HttpContext, username: str):
    pass

# Integer parameter
@app.get("/users/{user_id:int}")
async def get_user_by_id(ctx: HttpContext, user_id: int):
    pass

# Float parameter
@app.get("/prices/{price:float}")
async def get_by_price(ctx: HttpContext, price: float):
    pass

# Path parameter (captures slashes)
@app.get("/files/{file_path:path}")
async def get_file_by_path(ctx: HttpContext, file_path: str):
    pass
```

##  Query Parameters

Query parameters provide filtering, sorting, pagination, and search capabilities. Document them explicitly using the `parameters` argument:

```python
from sillo.openapi.models import Query
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
async def list_users(ctx: HttpContext):
    # Extract query parameters
    limit = int(ctx.query_params.get('limit', 20))
    offset = int(ctx.query_params.get('offset', 0))
    search = ctx.query_params.get('search')
    status = ctx.query_params.get('status', 'active')
    sort_by = ctx.query_params.get('sort_by', 'created_at')
    sort_order = ctx.query_params.get('sort_order', 'desc')
    
    # Apply filters and return results
    return {
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
    }
```

###  Advanced Query Parameter Patterns

```python
# Array parameters
from sillo import HttpContext

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
async def list_products(ctx: HttpContext):
    categories = ctx.query_params.getlist('categories')
    price_range = ctx.query_params.get('price_range', '').split(',')
    
    return {
        "products": [],
        "filters": {
            "categories": categories,
            "price_range": price_range
        }
    }

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
async def list_articles(ctx: HttpContext):
    published = ctx.query_params.get('published', 'true').lower() == 'true'
    featured = ctx.query_params.get('featured', '').lower() == 'true'
    
    return {
        "articles": [],
        "filters": {"published": published, "featured": featured}
    }
```

##  Header Parameters

Headers are used for authentication, content negotiation, client information, and custom metadata:

```python
from sillo.openapi.models import Header
from sillo import HttpContext

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
            description="Unique identifier for ctx tracing",
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
async def get_current_user(ctx: HttpContext):
    # Extract headers
    auth_header = ctx.headers.get('Authorization')
    request_id = ctx.headers.get('X-Request-ID')
    language = ctx.headers.get('Accept-Language', 'en')
    client_version = ctx.headers.get('X-Client-Version')
    
    return {
        "user": {"id": 123, "username": "current_user"},
        "request_id": request_id,
        "language": language,
        "client_version": client_version
    }
```

##  Cookie Parameters

Cookie parameters are used for session management, user preferences, and tracking:

```python
from sillo.openapi.models import Cookie
from sillo import HttpContext, json

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
async def get_dashboard(ctx: HttpContext):
    # Extract cookies
    session_id = ctx.cookies.get('session_id')
    theme = ctx.cookies.get('theme', 'auto')
    timezone = ctx.cookies.get('timezone', 'UTC')
    
    if not session_id:
        return json({
            "error": "Session required"
        }, status_code=401)
    
    return {
        "dashboard": {"widgets": []},
        "preferences": {
            "theme": theme,
            "timezone": timezone
        }
    }
```


###  Complex Parameter Schemas

```python
from sillo import HttpContext, json

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
async def get_analytics_report(ctx: HttpContext):
    date_range = ctx.query_params.get('date_range')
    metrics = ctx.query_params.getlist('metrics')
    granularity = ctx.query_params.get('granularity', 'day')
    
    # Validate date range format
    try:
        start_date, end_date = date_range.split(':')
        # Additional validation logic
    except ValueError:
        return json({
            "error": "Invalid date range format. Use YYYY-MM-DD:YYYY-MM-DD"
        }, status_code=400)
    
    return {
        "report": {
            "date_range": {"start": start_date, "end": end_date},
            "metrics": metrics,
            "granularity": granularity,
            "data": []
        }
    }
```

###  Parameter Dependencies

Document parameters that depend on each other:

```python
from sillo import HttpContext, json

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
async def search(ctx: HttpContext):
    query = ctx.query_params.get('q')
    category = ctx.query_params.get('category')
    advanced = ctx.query_params.get('advanced', 'false').lower() == 'true'
    
    if not query and not category:
        return json({
            "error": "Either 'q' or 'category' parameter is required"
        }, status_code=400)
    
    if advanced and not query:
        return json({
            "error": "Advanced search requires 'q' parameter"
        }, status_code=400)
    
    return {
        "results": [],
        "query": query,
        "category": category,
        "advanced": advanced
    }
```

##  Best Practices

###  Parameter Naming Conventions

```python
# Use consistent naming patterns
from sillo import HttpContext

@app.get("/users", parameters=[
    Query(name="user_id"),                       # snake_case for multi-word
    Query(name="limit"),                         # lowercase for single word
    Query(name="sort_by"),                       # descriptive names
    Header(name="X-API-Key"),                    # X- prefix for custom headers
])
async def list_users(ctx: HttpContext): ...


# Avoid ambiguous names
bad_id = Query(name="id")                      # Which ID?
bad_type = Query(name="type")                  # Type of what?

# Prefer specific ones
good_id = Query(name="user_id")                # Clear and specific
good_type = Query(name="content_type")         # Descriptive
```

###  Parameter Documentation

```python
from sillo import HttpContext

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
async def handler(ctx: HttpContext): ...
```

###  Parameter Validation

```python
from sillo import HttpContext, json

def validate_date_range(date_range: str) -> bool:
    """Validate date range parameter format"""
    try:
        start, end = date_range.split(':')
        # Additional validation logic
        return True
    except ValueError:
        return False

@app.get("/reports")
async def get_reports(ctx: HttpContext):
    date_range = ctx.query_params.get('date_range')
    
    if date_range and not validate_date_range(date_range):
        return json({
            "error": "Invalid date range format"
        }, status_code=400)
```

Request parameters are essential for creating flexible, powerful APIs. Proper documentation ensures that API consumers understand how to use your endpoints effectively and helps prevent integration issues.


##  Parameter design decisions that outlive the code

Parameter names and shapes are the part of an API hardest to change,
because clients hard-code them and a wrong name fails silently as a
default. Four decisions worth making once.

**Query or path?** Path segments identify a resource; query parameters
modify a request. `/orders/42` and `/orders?status=open` are both right.
`/orders?id=42` and `/orders/open` are both wrong, and the second is
worse because it looks like a resource and is not.

**Optional or required?** A required query parameter is unusual and often a
design smell. If it is genuinely required to identify what you are fetching, it
probably belongs in the path. Optional parameters with sensible defaults let a
client start with the simple call and add precision later.

**Repeated or delimited?** `?tag=a&tag=b` and `?tags=a,b` both work, and
the first is more standard and handles values containing commas. Pick one
convention for the whole API; supporting both accidentally means neither
is documented correctly.

**Flat or nested?** Query strings have no native nesting, and every convention
for faking it (`filter[status]`, `filter.status`) is a convention someone has
to learn. Flat parameters with prefixed names document better and generate
better clients.

##  Documenting for the client, not the implementation

The name a client sees is the one in the schema, which is where `alias`
earns its place. An internal field called `q` should be documented as
`query` if that is clearer, and a parameter that must be called `from`
cannot be a Python identifier at all.

Descriptions do the work names cannot. `page_size` is self-evident; `window` is
not, does it mean seconds, a count, a named period? One sentence in
`description=` prevents the support ticket.

Examples do more than descriptions for anything with format. A parameter
described as "the region code" with `examples=["eu-west-1"]` answers
casing, separator, and length in one glance, and the interactive UI
prefills it so the first attempt succeeds.

Mark deprecated parameters with `deprecated=True` rather than removing
them. The flag appears in the schema and in the UI, generated clients
surface it as a deprecation warning, and you get a release of notice
instead of a support incident.

##  Constraints are documentation

Every constraint you declare is published as JSON Schema, so `ge=1` and
`le=100` on a page size are not just enforcement. They tell a client exactly
what range to offer in a UI, and they let contract-testing tools probe the
boundary automatically.

The reverse is also true: a limit enforced in handler code rather than in
the constraint is invisible to every consumer of the schema. If the rule
can be expressed as a constraint, express it there.


##  Pagination parameters deserve special care

Pagination appears on most collection endpoints, and inconsistency across
them is the thing integrators complain about most.

Pick one scheme for the whole API. Page-and-size, limit-and-offset, and
cursor are all defensible; using all three across different endpoints is
not, because a client has to write three pagination implementations.

Document the maximum. A `page_size` with `le=100` published in the schema
tells a client the ceiling before they discover it through a 422. Without
it, someone will request ten thousand and build a UI around the response
they got in staging.

Document the ordering. Pagination without a guaranteed order returns
rows that repeat and rows that vanish between pages, and clients cannot
work around what they do not know. Say which field the results are
ordered by, and whether the client can change it.
