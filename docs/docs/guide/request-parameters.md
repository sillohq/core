---
title: Request Parameters
description: Extract query, header, and cookie parameters in Nexios handlers and dependencies
---

# Request Parameters

Nexios provides a clean, declarative way to extract query parameters, HTTP headers, and cookies directly in your handlers and dependencies using `Query`, `Header`, and `Cookie` parameter extractors.

## Quick Example

```python
from nexios import NexiosApp, Query, Header, Cookie

app = NexiosApp()

@app.get("/search")
async def search(
    request, response,
    q: str = Query(""),
    limit: int = Query(10),
    authorization: str = Header()
):
    return {"query": q, "limit": limit, "auth": authorization}
```

## Query Parameters

Use `Query()` to extract query string parameters with automatic type conversion.

### Basic Usage

```python
@app.get("/items")
async def get_items(
    request, response,
    page: int = Query(1),
    limit: int = Query(10)
):
    return {"page": page, "limit": limit}
```

**Request:** `GET /items?page=2&limit=20`
**Result:** `{"page": 2, "limit": 20}`

### With Defaults

```python
@app.get("/search")
async def search(request, response, q: str = Query("default query")):
    return {"query": q}
```

**Request:** `GET /search`
**Result:** `{"query": "default query"}`

### No Default

When no default is provided, the parameter returns `None` if not present:

```python
@app.get("/filter")
async def filter(request, response, tag: str = Query()):
    return {"tag": tag}
```

### Type Conversion

`Query()` automatically converts string values to the type of the default:

| Default Type | Conversion |
|--------------|------------|
| `int` | `int(value)` |
| `float` | `float(value)` |
| `bool` | `"true"/"1"/"yes"` → `True`, others → `False` |
| `list[str]` | Split by comma |
| `str` | No conversion |

```python
@app.get("/convert")
async def convert(
    request, response,
    count: int = Query(0),
    price: float = Query(0.0),
    active: bool = Query(False)
):
    return {"count": count, "price": price, "active": active}
```

### With Alias

Use `alias` to map a different query parameter name:

```python
@app.get("/users")
async def users(request, response, page_num: int = Query(1, alias="page")):
    return {"page": page_num}
```

**Request:** `GET /users?page=5`
**Result:** `{"page": 5}`

### Required Parameters

Use `required=True` to enforce presence:

```python
@app.get("/search")
async def search(request, response, q: str = Query(required=True)):
    return {"query": q}
```

---

## Header Parameters

Use `Header()` to extract HTTP headers with automatic name conversion.

### Basic Usage

Header names are automatically converted from Python naming to HTTP canonical format:

| Parameter Name | Header Name |
|----------------|-------------|
| `authorization` | `Authorization` |
| `content_type` | `Content-Type` |
| `x_request_id` | `X-Request-Id` |
| `user_agent` | `User-Agent` |

```python
@app.get("/api")
async def api(request, response, authorization: str = Header()):
    return {"auth": authorization}
```

**Request:** `GET /api` with header `Authorization: Bearer token123`
**Result:** `{"auth": "Bearer token123"}`

### With Default

```python
@app.get("/version")
async def version(request, response, api_key: str = Header(default="guest")):
    return {"api_key": api_key}
```

### Custom Header Name

Use `alias` for non-standard or custom header names:

```python
@app.get("/custom")
async def custom(request, response, token: str = Header(alias="X-API-Token")):
    return {"token": token}
```

**Request:** `GET /custom` with header `X-API-Token: secret123`
**Result:** `{"token": "secret123"}`

---

## Cookie Parameters

Use `Cookie()` to extract cookie values.

### Basic Usage

```python
@app.get("/settings")
async def settings(request, response, theme: str = Cookie("light")):
    return {"theme": theme}
```

**Request:** `GET /settings` with cookie `theme=dark`
**Result:** `{"theme": "dark"}`

### No Default

```python
@app.get("/session")
async def session(request, response, session_id: str = Cookie()):
    return {"session": session_id}
```

---

## Using in Nested Dependencies

Parameter extractors work seamlessly in nested dependencies—no need for `Context`:

### Query in Dependency

```python
def get_pagination(page: int = Query(1), limit: int = Query(10)):
    return {"page": page, "limit": limit}

@app.get("/items")
async def get_items(
    request, response,
    pagination: dict = Depend(get_pagination)
):
    return {"items": [], "pagination": pagination}
```

**Request:** `GET /items?page=3&limit=25`
**Result:** `{"items": [], "pagination": {"page": 3, "limit": 25}}`

### Header in Dependency

```python
def get_auth(authorization: str = Header()):
    if not authorization:
        raise ValueError("No authorization")
    return {"token": authorization}

@app.get("/profile")
async def profile(request, response, auth: dict = Depend(get_auth)):
    return auth
```

### Cookie in Dependency

```python
def get_preferences(theme: str = Cookie("dark"), lang: str = Cookie("en")):
    return {"theme": theme, "language": lang}

@app.get("/settings")
async def settings(request, response, prefs: dict = Depend(get_preferences)):
    return prefs
```

### Mixed Parameters in Dependency

```python
def get_context(
    page: int = Query(1),
    authorization: str = Header(),
    theme: str = Cookie("dark")
):
    return {"page": page, "auth": authorization, "theme": theme}

@app.get("/dashboard")
async def dashboard(request, response, ctx: dict = Depend(get_context)):
    return ctx
```

---

## Comparison: Parameters vs Context

Nexios provides two ways to access request data in dependencies:

### Using Parameters (Recommended)

```python
from nexios import Query, Header, Cookie, Depend

def get_user_data(
    page: int = Query(1),
    authorization: str = Header()
):
    return {"page": page, "token": authorization}

@app.get("/data")
async def get_data(request, response, data: dict = Depend(get_user_data)):
    return data
```

**Advantages:**
- Clean, declarative API
- Automatic type conversion
- Works with nested dependencies
- Self-documenting parameters

### Using Context (Legacy)

```python
from nexios import Depend
from nexios.dependencies import Context

def get_user_data(context: Context = None):
    page = context.request.query_params.get("page", "1")
    authorization = context.request.headers.get("Authorization")
    return {"page": page, "token": authorization}
```

**Disadvantages:**
- Manual type conversion required
- More verbose
- Accessing request attributes directly

::: tip Recommendation
Use `Query`, `Header`, and `Cookie` parameter extractors in dependencies. They provide cleaner code, automatic type conversion, and better testability.
:::

---

## OpenAPI Integration

Parameters automatically appear in your OpenAPI documentation. Nexios generates proper OpenAPI parameter objects with correct types, locations, and default values.

### Example OpenAPI Output

Given this handler:

```python
@app.get("/items")
async def get_items(
    request, response,
    page: int = Query(1),
    limit: int = Query(10),
    authorization: str = Header()
):
    return {"page": page}
```

The generated OpenAPI spec includes:

```json
{
  "/items": {
    "get": {
      "parameters": [
        {
          "name": "page",
          "in": "query",
          "schema": {"type": "integer", "default": 1},
          "required": false
        },
        {
          "name": "limit",
          "in": "query",
          "schema": {"type": "integer", "default": 10},
          "required": false
        },
        {
          "name": "Authorization",
          "in": "header",
          "schema": {"type": "string"},
          "required": true
        }
      ]
    }
  }
}
```

### Features

- **Automatic type inference**: `int` → `integer`, `float` → `number`, `bool` → `boolean`, `str` → `string`
- **Header name conversion**: `authorization` → `Authorization`, `x_request_id` → `X-Request-Id`
- **Default values**: Included in schema for documentation
- **Required status**: Automatically determined from `required=True` or when no default is provided
- **Aliases**: Respected for custom parameter names

---

## API Reference

### Query(default=..., *, alias=None, required=False)

Extract query parameters.

| Parameter | Type | Description |
|-----------|------|-------------|
| `default` | Any | Default value if param not provided |
| `alias` | str | Custom query parameter name |
| `required` | bool | Raise error if param missing |

### Header(default=..., *, alias=None, required=False)

Extract HTTP headers. Auto-converts parameter names to canonical header names.

| Parameter | Type | Description |
|-----------|------|-------------|
| `default` | Any | Default value if header not present |
| `alias` | str | Custom header name |
| `required` | bool | Raise error if header missing |

### Cookie(default=..., *, alias=None, required=False)

Extract cookie values.

| Parameter | Type | Description |
|-----------|------|-------------|
| `default` | Any | Default value if cookie not present |
| `alias` | str | Custom cookie name |
| `required` | bool | Raise error if cookie missing |
