# Response

The `NexiosResponse` class provides a fluent interface for building HTTP responses with support for various content types, headers, cookies, caching, and more.

## 📋 Class Definition

```python
class NexiosResponse:
    def __init__(self, request: Request)
```

The response object is typically provided automatically in route handlers and should not be instantiated manually.

## 📄 Content Response Methods

### json()
Send JSON response with automatic serialization.

```python
async def handler(request: Request, response: Response):
    data = {
        "users": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ],
        "total": 2
    }
    
    return response.json(
        data,
        status_code=200,
        headers={"X-Custom": "value"},
        indent=2,              # Pretty print JSON
        ensure_ascii=False     # Allow unicode characters
    )
```

**Parameters**:
- `data` (Union[str, List[Any], Dict[str, Any]]): Data to serialize as JSON
- `status_code` (Optional[int]): HTTP status code (default: 200)
- `headers` (Dict[str, Any]): Additional headers
- `indent` (Optional[int]): JSON indentation for pretty printing
- `ensure_ascii` (bool): Whether to escape non-ASCII characters

### html()
Send HTML response.

```python
async def handler(request: Request, response: Response):
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Welcome</title></head>
    <body>
        <h1>Hello, World!</h1>
        <p>Welcome to our application.</p>
    </body>
    </html>
    """
    
    return response.html(
        html_content,
        status_code=200,
        headers={"Cache-Control": "no-cache"}
    )
```

**Parameters**:
- `content` (str): HTML content
- `status_code` (Optional[int]): HTTP status code
- `headers` (Dict[str, Any]): Additional headers

### text()
Send plain text response.

```python
async def handler(request: Request, response: Response):
    return response.text(
        "Hello, World!",
        status_code=200,
        headers={"Content-Language": "en"}
    )
```

**Parameters**:
- `content` (JSONType): Text content
- `status_code` (Optional[int]): HTTP status code
- `headers` (Dict[str, Any]): Additional headers

### file()
Send file response with proper headers.

```python
async def handler(request: Request, response: Response):
    # Serve file inline (display in browser)
    return response.file(
        path="/path/to/document.pdf",
        filename="report.pdf",
        content_disposition_type="inline"
    )
```

**Parameters**:
- `path` (str): File system path to the file
- `filename` (Optional[str]): Custom filename for download
- `content_disposition_type` (str): "inline" or "attachment"

### download()
Force file download with attachment disposition.

```python
async def handler(request: Request, response: Response):
    # Force download
    return response.download(
        path="/path/to/archive.zip",
        filename="backup.zip"
    )
```

**Parameters**:
- `path` (str): File system path
- `filename` (Optional[str]): Download filename

### stream()
Send streaming response for large content or real-time data.

```python
async def handler(request: Request, response: Response):
    async def generate_data():
        for i in range(1000):
            yield f"data chunk {i}\n"
            await asyncio.sleep(0.1)  # Simulate processing
    
    return response.stream(
        generate_data(),
        content_type="text/plain",
        status_code=200
    )
```

**Parameters**:
- `iterator` (Generator): Async generator yielding content chunks
- `content_type` (str): MIME type for the content
- `status_code` (Optional[int]): HTTP status code

### redirect()
Send redirect response.

```python
async def handler(request: Request, response: Response):
    # Temporary redirect (302)
    return response.redirect("/new-location")
    
    # Permanent redirect (301)
    return response.redirect("/new-location", status_code=301)
    
    # External redirect
    return response.redirect("https://example.com")
```

**Parameters**:
- `url` (str): Target URL for redirection
- `status_code` (int): Redirect status code (default: 302)

### empty()
Send empty response (useful for 204 No Content).

```python
async def handler(request: Request, response: Response):
    # Delete operation successful
    await delete_user(user_id)
    return response.status(204).empty()
```

**Parameters**:
- `status_code` (Optional[int]): HTTP status code
- `headers` (Dict[str, Any]): Additional headers

## 🔢 Status Code Management

### status()
Set HTTP status code.

```python
async def handler(request: Request, response: Response):
    # Success responses
    return response.status(201).json({"created": True})  # Created
    return response.status(204).empty()                   # No Content
    
    # Client error responses
    return response.status(400).json({"error": "Bad Request"})
    return response.status(401).json({"error": "Unauthorized"})
    return response.status(404).json({"error": "Not Found"})
    
    # Server error responses
    return response.status(500).json({"error": "Internal Server Error"})
```

## 📋 Header Management

### set_header()
Set individual response header.

```python
async def handler(request: Request, response: Response):
    return (response
            .set_header("X-API-Version", "1.0")
            .set_header("X-Rate-Limit", "100")
            .set_header("Cache-Control", "max-age=3600")
            .json({"data": "response"}))
```

**Parameters**:
- `key` (str): Header name
- `value` (str): Header value
- `override` (bool): Whether to replace existing header

### set_headers()
Set multiple headers at once.

```python
async def handler(request: Request, response: Response):
    headers = {
        "X-API-Version": "1.0",
        "X-Rate-Limit": "100",
        "Access-Control-Allow-Origin": "*"
    }
    
    return (response
            .set_headers(headers)
            .json({"data": "response"}))
```

**Parameters**:
- `headers` (Dict[str, str]): Dictionary of headers
- `override_all` (bool): Replace all existing headers

### remove_header()
Remove a specific header.

```python
async def handler(request: Request, response: Response):
    return (response
            .set_header("X-Debug", "enabled")
            .remove_header("X-Debug")  # Remove it
            .json({"data": "clean response"}))
```

## 🍪 Cookie Management

### set_cookie()
Set response cookie with comprehensive options.

```python
async def handler(request: Request, response: Response):
    return (response
            .set_cookie(
                key="session_id",
                value="abc123",
                max_age=3600,              # 1 hour
                path="/",
                domain=".example.com",
                secure=True,               # HTTPS only
                httponly=True,             # No JavaScript access
                samesite="strict"          # CSRF protection
            )
            .json({"message": "Cookie set"}))
```

**Parameters**:
- `key` (str): Cookie name
- `value` (str): Cookie value
- `max_age` (Optional[int]): Expiry in seconds
- `expires` (Optional[Union[str, datetime, int]]): Expiry date
- `path` (str): Cookie path (default: "/")
- `domain` (Optional[str]): Cookie domain
- `secure` (bool): HTTPS only (default: True)
- `httponly` (bool): No JavaScript access (default: False)
- `samesite` (Optional[Literal["lax", "strict", "none"]]): SameSite policy

### set_permanent_cookie()
Set long-lasting cookie (10 years).

```python
async def handler(request: Request, response: Response):
    return (response
            .set_permanent_cookie("user_preference", "dark_mode")
            .json({"message": "Preference saved"}))
```

### delete_cookie()
Delete a cookie by setting expiry to past.

```python
async def handler(request: Request, response: Response):
    return (response
            .delete_cookie("session_id", path="/", domain=".example.com")
            .json({"message": "Logged out"}))
```

### set_cookies()
Set multiple cookies at once.

```python
async def handler(request: Request, response: Response):
    cookies = [
        {"key": "session_id", "value": "abc123", "httponly": True},
        {"key": "theme", "value": "dark", "max_age": 86400}
    ]
    
    return (response
            .set_cookies(cookies)
            .json({"message": "Cookies set"}))
```

## 💾 Caching Control

### cache()
Enable response caching.

```python
async def handler(request: Request, response: Response):
    # Cache for 1 hour (private cache)
    return (response
            .cache(max_age=3600, private=True)
            .json({"data": "cacheable content"}))
    
    # Public cache for CDN
    return (response
            .cache(max_age=86400, private=False)
            .json({"static": "public data"}))
```

**Parameters**:
- `max_age` (int): Cache duration in seconds (default: 3600)
- `private` (bool): Private vs public cache (default: True)

### no_cache()
Disable caching completely.

```python
async def handler(request: Request, response: Response):
    # Sensitive data that should never be cached
    return (response
            .no_cache()
            .json({"sensitive": "user data"}))
```

## 🔒 Security Headers

### add_csp_header()
Add Content Security Policy header.

```python
async def handler(request: Request, response: Response):
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:;"
    )
    
    return (response
            .add_csp_header(csp_policy)
            .html("<html>...</html>"))
```

## 📄 Pagination Support

### paginate()
Paginate response data (synchronous).

```python
async def handler(request: Request, response: Response):
    all_users = await get_all_users()
    
    return response.paginate(
        objects=all_users,
        strategy="page_number",  # or "limit_offset", "cursor"
        page_size=20,
        page=int(request.query_params.get("page", 1))
    )
```

### apaginate()
Paginate response data (asynchronous).

```python
async def handler(request: Request, response: Response):
    all_users = await get_all_users()
    
    return await response.apaginate(
        objects=all_users,
        strategy="limit_offset",
        limit=int(request.query_params.get("limit", 20)),
        offset=int(request.query_params.get("offset", 0))
    )
```

## 📊 Response Properties

### status_code: int
Current HTTP status code.

```python
async def handler(request: Request, response: Response):
    response.status(404)
    current_status = response.status_code  # 404
```

### headers: MutableHeaders
Response headers object.

```python
async def handler(request: Request, response: Response):
    response.set_header("X-Custom", "value")
    custom_header = response.headers.get("X-Custom")  # "value"
    
    # Check if header exists
    has_custom = response.has_header("X-Custom")  # True
```

### content_type: Optional[str]
Current content type.

```python
async def handler(request: Request, response: Response):
    response.json({"data": "test"})
    content_type = response.content_type  # "application/json"
```

### content_length: str
Content length of the response body.

```python
async def handler(request: Request, response: Response):
    response.text("Hello, World!")
    length = response.content_length  # "13"
```

### body: bytes
Raw response body.

```python
async def handler(request: Request, response: Response):
    response.text("Hello")
    raw_body = response.body  # b"Hello"
```

## 🚀 Advanced Usage

### Custom Response Classes

```python
async def handler(request: Request, response: Response):
    # Create custom response
    custom_response = BaseResponse(
        body="Custom content",
        status_code=200,
        headers={"X-Custom": "header"},
        content_type="text/plain"
    )
    
    return response.make_response(custom_response)
```

### Conditional Responses

```python
async def handler(request: Request, response: Response):
    user_id = request.path_params.get("user_id")
    user = await get_user(user_id)
    
    if not user:
        return response.status(404).json({
            "error": "User not found",
            "code": "USER_NOT_FOUND"
        })
    
    if not user.is_active:
        return response.status(403).json({
            "error": "User account is disabled",
            "code": "ACCOUNT_DISABLED"
        })
    
    return response.json({
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    })
```

### File Streaming with Progress

```python
async def handler(request: Request, response: Response):
    file_path = "/path/to/large/file.zip"
    file_size = os.path.getsize(file_path)
    
    async def stream_file():
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)  # 8KB chunks
                if not chunk:
                    break
                yield chunk
    
    return (response
            .set_header("Content-Length", str(file_size))
            .set_header("Content-Disposition", "attachment; filename=file.zip")
            .stream(stream_file(), content_type="application/zip"))
```

### API Response Patterns

```python
# Success response with metadata
async def list_users(request: Request, response: Response):
    users = await get_users()
    
    return response.json({
        "data": users,
        "meta": {
            "total": len(users),
            "page": 1,
            "per_page": 20
        },
        "links": {
            "self": str(request.url),
            "next": None,
            "prev": None
        }
    })

# Error response with details
async def create_user(request: Request, response: Response):
    try:
        user_data = await request.json
        user = await create_user_service(user_data)
        
        return response.status(201).json({
            "data": user,
            "message": "User created successfully"
        })
        
    except ValidationError as e:
        return response.status(400).json({
            "error": "Validation failed",
            "details": e.errors(),
            "code": "VALIDATION_ERROR"
        })
    except DuplicateEmailError:
        return response.status(409).json({
            "error": "Email already exists",
            "code": "DUPLICATE_EMAIL"
        })
```

### Content Negotiation

```python
async def handler(request: Request, response: Response):
    data = {"message": "Hello, World!"}
    
    # Check Accept header for content negotiation
    accept_header = request.headers.get("accept", "")
    
    if "application/json" in accept_header:
        return response.json(data)
    elif "text/html" in accept_header:
        html = f"<h1>{data['message']}</h1>"
        return response.html(html)
    elif "text/plain" in accept_header:
        return response.text(data["message"])
    else:
        # Default to JSON
        return response.json(data)
```

### Response Middleware Integration

```python
# Custom response processing
async def response_middleware(request, response, call_next):
    result = await call_next()
    
    # Add security headers to all responses
    result.set_header("X-Content-Type-Options", "nosniff")
    result.set_header("X-Frame-Options", "DENY")
    result.set_header("X-XSS-Protection", "1; mode=block")
    
    # Add request ID for tracing
    request_id = request.headers.get("X-Request-ID", "unknown")
    result.set_header("X-Request-ID", request_id)
    
    return result
```

## ⚠️ Error Handling

### Validation Errors

```python
from pydantic import BaseModel, ValidationError

class UserCreate(BaseModel):
    name: str
    email: str
    age: int

async def create_user(request: Request, response: Response):
    try:
        json_data = await request.json
        user_data = UserCreate(**json_data)
        
        # Process valid data
        user = await save_user(user_data)
        return response.status(201).json(user)
        
    except ValidationError as e:
        return response.status(400).json({
            "error": "Invalid input data",
            "details": e.errors()
        })
    except json.JSONDecodeError:
        return response.status(400).json({
            "error": "Invalid JSON format"
        })
```

### File Operation Errors

```python
async def serve_file(request: Request, response: Response):
    file_path = request.path_params["file_path"]
    
    try:
        # Security check
        if ".." in file_path or file_path.startswith("/"):
            return response.status(400).json({"error": "Invalid file path"})
        
        full_path = f"/safe/directory/{file_path}"
        
        if not os.path.exists(full_path):
            return response.status(404).json({"error": "File not found"})
        
        if not os.path.isfile(full_path):
            return response.status(400).json({"error": "Not a file"})
        
        return response.file(full_path)
        
    except PermissionError:
        return response.status(403).json({"error": "Access denied"})
    except Exception as e:
        logger.error(f"File serving error: {e}")
        return response.status(500).json({"error": "Internal server error"})
```

## ✨ Best Practices

1. **Use appropriate status codes** for different scenarios
2. **Set proper content types** for different response formats
3. **Include security headers** for web applications
4. **Use caching wisely** to improve performance
5. **Implement proper error handling** with meaningful messages
6. **Use streaming** for large files or real-time data
7. **Follow REST conventions** for API responses
8. **Include metadata** in API responses (pagination, links, etc.)
9. **Use content negotiation** for multi-format APIs
10. **Set appropriate cookie security** flags

## 🔢 Response Status Codes

### Success (2xx)
- `200 OK` - Standard success response
- `201 Created` - Resource created successfully
- `202 Accepted` - Request accepted for processing
- `204 No Content` - Success with no response body

### Redirection (3xx)
- `301 Moved Permanently` - Permanent redirect
- `302 Found` - Temporary redirect
- `304 Not Modified` - Cached version is still valid

### Client Error (4xx)
- `400 Bad Request` - Invalid request format
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Access denied
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict
- `422 Unprocessable Entity` - Validation failed

### Server Error (5xx)
- `500 Internal Server Error` - Unexpected server error
- `502 Bad Gateway` - Upstream server error
- `503 Service Unavailable` - Service temporarily unavailable

## 🔍 See Also

- [Request](./request.md) - HTTP request handling
- [Middleware](./middleware.md) - Response middleware
- [Testing](./testclient.md) - Testing utilities