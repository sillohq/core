---
title: Headers
description: Headers are a fundamental part of HTTP requests and responses, carrying metadata about the message body, client capabilities, server information, and more. Nexios provides comprehensive tools for working with headers in both requests and responses.
head:
  - - meta
    - property: og:title
      content: Headers
  - - meta
    - property: og:description
      content: Headers are a fundamental part of HTTP requests and responses, carrying metadata about the message body, client capabilities, server information, and more. Nexios provides comprehensive tools for working with headers in both requests and responses.
---
#  Headers

Access incoming request headers through the `request.headers` property, which provides a case-insensitive dictionary-like interface:

```python{5,6}
from nexios import NexiosApp
app = NexiosApp()
@app.get("/")
async def show_headers(request, response):
    user_agent = request.headers.get("user-agent")
    accept_language = request.headers.get("accept-language")
    return {
        "user_agent": user_agent,
        "accept_language": accept_language
    }
```

### Common Request Headers

| Header | Description | Example |
|--------|-------------|---------|
| `Accept` | Content types the client can process | `application/json, text/html` |
| `Authorization` | Credentials for authentication | `Bearer xyz123` |
| `Content-Type` | Media type of the request body | `application/json` |
| `Cookie` | Cookies sent by the client | `session_id=abc123` |
| `User-Agent` | Client application information | `Mozilla/5.0` |
| `X-Requested-With` | Indicates AJAX request | `XMLHttpRequest` |

::: tip  Tip
Nexios normalizes header names to lowercase, so `request.headers.get("User-Agent")` and `request.headers.get("user-agent")` are equivalent.
:::

##  Response Headers

Set response headers using the `response.set_header()` method or by passing a headers dictionary:

```python{5,6}
from nexios import NexiosApp
app = NexiosApp()
@app.get("/")
async def set_headers(request, response):
    response.set_header("X-Custom-Header", "Custom Value")
    response.set_header("Cache-Control", "no-store")
    return response.text("Hello, World!")
```

### Common Response Headers

| Header | Description | Example |
|--------|-------------|---------|
| `Content-Type` | Media type of the response | `text/html; charset=utf-8` |
| `Cache-Control` | Caching directives | `max-age=3600` |
| `Set-Cookie` | Sets cookies on client | `session_id=abc123; Path=/` |
| `Location` | URL for redirects | `https://example.com/new` |
| `X-Frame-Options` | Clickjacking protection | `DENY` |
| `Content-Security-Policy` | Security policy | `default-src 'self'` |

##  Setting Headers In Middleware

In middleware, you need to modify headers after the response has been created by the route handler.

### Correct Middleware Pattern

Always set headers **after** calling `await call_next()`:

```python
async def cors_middleware(request, response, call_next):
    response = await call_next()
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE")
    response.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    return response
```

### Common Middleware Use Cases

#### CORS Headers
```python
async def cors_middleware(request, response, call_next):
    response = await call_next()
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    response.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    response.set_header("Access-Control-Max-Age", "86400")
    return response
```

#### Security Headers
```python
async def security_middleware(request, response, call_next):
    response = await call_next()
    response.set_header("X-Content-Type-Options", "nosniff")
    response.set_header("X-Frame-Options", "DENY")
    response.set_header("X-XSS-Protection", "1; mode=block")
    response.set_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response
```

#### Request ID Tracking
```python
async def request_id_middleware(request, response, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next()
    response.set_header("X-Request-ID", request_id)
    return response
```

::: tip Best Practice

In route handlers, prefer passing headers as arguments to response methods for cleaner code:

```python
# Clean approach for handlers
@app.get("/api/data")
async def get_data(req, res):
    return res.json(
        {"data": "success"}, 
        headers={
            "X-API-Version": "1.0",
            "Cache-Control": "no-cache"
        }
    )
```

Use `set_header()` primarily in middleware where you need to modify responses after they're created.

:::

##  Header Manipulation Methods

Nexios provides several methods for working with headers:

### Request Header Methods
- `request.headers.get(key, default=None)` - Get a header value
- `request.headers.items()` - Get all headers as key-value pairs
- `request.headers.keys()` - Get all header names
- `request.headers.values()` - Get all header values

### Response Header Methods
- `response.set_header(key, value, override=False)` - Set a header
- `response.remove_header(key)` - Remove a header
- `response.has_header(key)` - Check if header exists
- `response.set_headers(headers_dict, override_all=False)` - Set multiple headers

##  Security Headers Best Practices

For enhanced security, consider these recommended headers:

```python
@app.middleware
async def add_security_headers(request, response, next):
    response.set_headers({
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'",
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload"
    })
    await next()
```

##  Performance Headers

Optimize client-side caching and resource loading:

```python
@app.middleware
async def add_performance_headers(request, response, next):
    if request.path.endswith(('.js', '.css', '.png', '.jpg')):
        response.set_header("Cache-Control", "public, max-age=31536000, immutable")
    await next()
```

##  Cookie Headers

Cookies are set via special `Set-Cookie` headers:

```python
@app.get("/login")
async def login(request, response):
    response.set_cookie(
        key="session_id",
        value="abc123",
        max_age=3600,
        secure=True,
        httponly=True,
        samesite="strict"
    )
    return response.redirect("/dashboard")
```

##  Conditional Headers

Handle conditional requests with these headers:

| Header | Purpose | Example |
|--------|---------|---------|
| `If-Modified-Since` | Check if resource changed | `Sat, 01 Jan 2022 00:00:00 GMT` |
| `If-None-Match` | Check ETag match | `"abc123"` |
| `ETag` | Resource version identifier | `W/"xyz456"` |
| `Last-Modified` | Resource modification time | `Sat, 01 Jan 2022 00:00:00 GMT` |

##  Restricted Headers

Some headers are restricted and cannot be modified:

- `Content-Length` (automatically calculated)
- `Connection`
- `Transfer-Encoding`
- `Host`

::: warning ⚠️ Warning
Always set headers after the request is processed in middleware when modifying responses. Setting headers too early may result in them being overwritten.
:::

##  Further Reading

- [MDN HTTP Headers Reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers)
- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [RFC 7231: HTTP/1.1 Semantics](https://tools.ietf.org/html/rfc7231)

