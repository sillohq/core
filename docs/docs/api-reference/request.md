# Request

The `Request` class represents an incoming HTTP request and provides comprehensive access to request data, headers, body content, and metadata.

## 📋 Class Definition

```python
class Request(HTTPConnection):
    def __init__(
        self, 
        scope: Scope, 
        receive: Receive = empty_receive, 
        send: Send = empty_send
    )
```

## 📊 Core Properties

### Basic Request Information

#### method: str
The HTTP method of the request (GET, POST, PUT, DELETE, etc.).

```python
@app.get("/example")
async def handler(request: Request, response: Response):
    if request.method == "GET":
        return response.json({"method": "GET request"})
```

#### url: URL
Complete URL object with scheme, host, port, path, and query parameters.

```python
async def handler(request: Request, response: Response):
    full_url = str(request.url)  # "https://example.com/api/users?page=1"
    scheme = request.url.scheme  # "https"
    host = request.url.hostname  # "example.com"
    port = request.url.port      # 443
    path = request.url.path      # "/api/users"
    query = request.url.query    # "page=1"
```

#### path: str
The path portion of the URL.

```python
async def handler(request: Request, response: Response):
    current_path = request.path  # "/api/users/123"
```

#### headers: Headers
Case-insensitive dictionary-like object containing request headers.

```python
async def handler(request: Request, response: Response):
    content_type = request.headers.get("content-type")
    auth_header = request.headers.get("authorization")
    user_agent = request.headers.get("user-agent")
    
    # Check if header exists
    has_auth = "authorization" in request.headers
    
    # Get all values for a header (for headers that can appear multiple times)
    accept_values = request.headers.getlist("accept")
```

#### query_params: QueryParams
Dictionary-like object for accessing URL query parameters.

```python
async def handler(request: Request, response: Response):
    # URL: /search?q=python&category=programming&limit=10
    search_query = request.query_params.get("q")        # "python"
    category = request.query_params.get("category")     # "programming"
    limit = request.query_params.get("limit", "20")     # "10" (with default)
    
    # Get all parameters as dict
    all_params = dict(request.query_params)
    
    # Check if parameter exists
    has_filter = "filter" in request.query_params
```

#### path_params: Dict[str, Any]
Dictionary containing path parameters extracted from the URL pattern.

```python
@app.get("/users/{user_id}/posts/{post_id}")
async def handler(request: Request, response: Response):
    user_id = request.path_params["user_id"]    # From URL: /users/123/posts/456
    post_id = request.path_params["post_id"]    # post_id = "456"
    
    # Convert to appropriate types
    user_id_int = int(user_id)
    post_id_int = int(post_id)
```

#### cookies: Dict[str, str]
Dictionary containing request cookies.

```python
async def handler(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    user_pref = request.cookies.get("user_preference", "default")
    
    # Check if cookie exists
    has_session = "session_id" in request.cookies
```

### Client Information

#### client: Optional[Address]
Client address information (IP and port).

```python
async def handler(request: Request, response: Response):
    if request.client:
        client_ip = request.client.host    # "192.168.1.100"
        client_port = request.client.port  # 54321
```

#### user_agent: str
User-Agent header value.

```python
async def handler(request: Request, response: Response):
    user_agent = request.user_agent
    # "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36..."
```

#### origin: str
Origin header value or constructed from URL.

```python
async def handler(request: Request, response: Response):
    origin = request.origin  # "https://example.com"
```

#### referrer: str
Referer header value.

```python
async def handler(request: Request, response: Response):
    referrer = request.referrer  # "https://google.com/search?q=..."
```

### Content Properties

#### content_type: Optional[str]
Content-Type header value.

```python
async def handler(request: Request, response: Response):
    content_type = request.content_type
    if content_type == "application/json":
        data = await request.json
    elif content_type == "application/x-www-form-urlencoded":
        form_data = await request.form
```

#### content_length: int
Content-Length header value as integer.

```python
async def handler(request: Request, response: Response):
    size = request.content_length  # Size in bytes
    if size > 1024 * 1024:  # 1MB
        return response.status(413).json({"error": "Request too large"})
```

## 📄 Body Content Access

### body: bytes
Raw request body as bytes.

```python
async def handler(request: Request, response: Response):
    raw_body = await request.body
    # Process raw bytes
    if len(raw_body) > 0:
        # Handle binary data
        pass
```

### text: str
Request body decoded as text.

```python
async def handler(request: Request, response: Response):
    text_content = await request.text
    # Process plain text content
    lines = text_content.split('\n')
```

### json: Dict[str, Any]
Parse request body as JSON.

```python
async def handler(request: Request, response: Response):
    try:
        json_data = await request.json
        name = json_data.get("name")
        email = json_data.get("email")
        
        # Validate required fields
        if not name or not email:
            return response.status(400).json({"error": "Missing required fields"})
            
    except json.JSONDecodeError:
        return response.status(400).json({"error": "Invalid JSON"})
```

### form: FormData
Parse form data (both URL-encoded and multipart).

```python
async def handler(request: Request, response: Response):
    form_data = await request.form
    
    # Access form fields
    username = form_data.get("username")
    password = form_data.get("password")
    
    # Handle multiple values for same field name
    categories = form_data.getlist("category")
```

### files: Dict[str, UploadedFile]
Access uploaded files from multipart form data.

```python
async def handler(request: Request, response: Response):
    files = await request.files
    
    if "avatar" in files:
        avatar_file = files["avatar"]
        filename = avatar_file.filename
        content_type = avatar_file.content_type
        file_size = avatar_file.size
        
        # Read file content
        content = await avatar_file.read()
        
        # Save file
        with open(f"uploads/{filename}", "wb") as f:
            f.write(content)
```

## 🌊 Stream Processing

### stream()
Stream request body in chunks for large files.

```python
async def handler(request: Request, response: Response):
    total_size = 0
    async for chunk in request.stream():
        total_size += len(chunk)
        # Process chunk
        if total_size > MAX_FILE_SIZE:
            return response.status(413).json({"error": "File too large"})
```

## 🔐 Authentication & Session

### user: Optional[BaseUser]
Current authenticated user (requires auth middleware).

```python
async def handler(request: Request, response: Response):
    if request.user:
        user_id = request.user.id
        username = request.user.username
        is_admin = request.user.is_admin
    else:
        return response.status(401).json({"error": "Authentication required"})
```

### session: BaseSessionInterface
Session data (requires session middleware).

```python
async def handler(request: Request, response: Response):
    # Get session data
    user_id = request.session.get("user_id")
    cart_items = request.session.get("cart", [])
    
    # Set session data
    request.session["last_visit"] = datetime.now().isoformat()
    
    # Clear session
    request.session.clear()
```

## 🗂️ State Management

### state: State
Request-scoped state for sharing data between middleware and handlers.

```python
# In middleware
async def auth_middleware(request, response, call_next):
    token = request.headers.get("authorization")
    user = await verify_token(token)
    request.state.user = user
    return await call_next()

# In handler
async def handler(request: Request, response: Response):
    user = request.state.user  # Set by middleware
    return response.json({"user_id": user.id})
```

### app: NexiosApp
Reference to the main application instance.

```python
async def handler(request: Request, response: Response):
    # Access application state
    db = request.app.state["database"]
    cache = request.app.state["cache"]
    
    # Access configuration
    debug_mode = request.app.config.get("debug", False)
```

## 🔧 Utility Methods

### build_absolute_uri()
Build absolute URIs from relative paths.

```python
async def handler(request: Request, response: Response):
    # Build absolute URL
    profile_url = request.build_absolute_uri("/profile")
    # "https://example.com/profile"
    
    # With query parameters
    search_url = request.build_absolute_uri("/search", {"q": "python"})
    # "https://example.com/search?q=python"
```

### url_for()
Generate URLs for named routes.

```python
@app.get("/users/{user_id}", name="get_user")
async def get_user(request: Request, response: Response):
    user_id = request.path_params["user_id"]
    # ... handler logic

async def handler(request: Request, response: Response):
    user_url = request.url_for("get_user", user_id=123)
    # "/users/123"
```

### get_header()
Get header with default value.

```python
async def handler(request: Request, response: Response):
    api_key = request.get_header("X-API-Key", "default_key")
    content_type = request.get_header("Content-Type", "application/json")
```

### has_header()
Check if header exists.

```python
async def handler(request: Request, response: Response):
    if request.has_header("Authorization"):
        # Process authenticated request
        pass
    else:
        return response.status(401).json({"error": "Authentication required"})
```

### get_client_ip()
Get client IP address (handles proxy headers).

```python
async def handler(request: Request, response: Response):
    client_ip = request.get_client_ip()
    # Handles X-Forwarded-For and X-Real-IP headers
    
    # Log request
    logger.info(f"Request from {client_ip}: {request.method} {request.path}")
```

### is_method()
Check request method (case-insensitive).

```python
async def handler(request: Request, response: Response):
    if request.is_method("POST"):
        # Handle POST request
        data = await request.json
    elif request.is_method("GET"):
        # Handle GET request
        params = dict(request.query_params)
```

## 📝 Content Type Checks

### is_json: bool
Check if request content type is JSON.

```python
async def handler(request: Request, response: Response):
    if request.is_json:
        data = await request.json
    else:
        return response.status(400).json({"error": "JSON content required"})
```

### is_form: bool
Check if request is form data.

```python
async def handler(request: Request, response: Response):
    if request.is_form:
        form_data = await request.form
        username = form_data.get("username")
```

### is_multipart: bool
Check if request is multipart form data.

```python
async def handler(request: Request, response: Response):
    if request.is_multipart:
        files = await request.files
        if "upload" in files:
            # Process file upload
            pass
```

### is_urlencoded: bool
Check if request is URL-encoded form data.

```python
async def handler(request: Request, response: Response):
    if request.is_urlencoded:
        form_data = await request.form
        # Process form submission
```

## ✅ Request State Checks

### is_secure: bool
Check if request is using HTTPS.

```python
async def handler(request: Request, response: Response):
    if not request.is_secure:
        # Redirect to HTTPS
        secure_url = request.url.replace(scheme="https")
        return response.redirect(str(secure_url), status_code=301)
```

### is_ajax: bool
Check if request is an AJAX request.

```python
async def handler(request: Request, response: Response):
    if request.is_ajax:
        # Return JSON response for AJAX
        return response.json({"data": "ajax_data"})
    else:
        # Return HTML response for regular requests
        return response.html("<html>...</html>")
```

### accepts_html: bool
Check if client accepts HTML responses.

```python
async def handler(request: Request, response: Response):
    if request.accepts_html:
        return response.html("<h1>Welcome</h1>")
    else:
        return response.json({"message": "Welcome"})
```

### accepts_json: bool
Check if client accepts JSON responses.

```python
async def handler(request: Request, response: Response):
    data = {"users": [...]}
    
    if request.accepts_json:
        return response.json(data)
    else:
        # Return alternative format
        return response.text(str(data))
```

### has_body: bool
Check if request has a body.

```python
async def handler(request: Request, response: Response):
    if request.has_body:
        if request.is_json:
            data = await request.json
        elif request.is_form:
            data = await request.form
    else:
        return response.status(400).json({"error": "Request body required"})
```

### has_files: bool
Check if request contains uploaded files.

```python
async def handler(request: Request, response: Response):
    if request.has_files:
        files = await request.files
        # Process file uploads
    else:
        return response.status(400).json({"error": "File upload required"})
```

### is_authenticated: bool
Check if user is authenticated.

```python
async def handler(request: Request, response: Response):
    if not request.is_authenticated:
        return response.status(401).json({"error": "Authentication required"})
    
    # Process authenticated request
    user_data = {"id": request.user.id, "name": request.user.name}
    return response.json(user_data)
```

### has_session: bool
Check if session middleware is available.

```python
async def handler(request: Request, response: Response):
    if request.has_session:
        visit_count = request.session.get("visits", 0) + 1
        request.session["visits"] = visit_count
        return response.json({"visits": visit_count})
    else:
        return response.json({"message": "Session not available"})
```



### Streaming Large Requests

```python
async def upload_handler(request: Request, response: Response):
    if request.content_length > 100 * 1024 * 1024:  # 100MB
        return response.status(413).json({"error": "File too large"})
    
    # Stream processing for large files
    total_bytes = 0
    chunks = []
    
    async for chunk in request.stream():
        total_bytes += len(chunk)
        chunks.append(chunk)
        
        # Progress tracking
        if total_bytes % (1024 * 1024) == 0:  # Every MB
            print(f"Received {total_bytes // (1024 * 1024)}MB")
    
    # Combine chunks
    full_content = b''.join(chunks)
    
    return response.json({"received_bytes": total_bytes})
```

### Request Validation

```python
from pydantic import BaseModel, ValidationError

class UserCreateRequest(BaseModel):
    name: str
    email: str
    age: int

async def create_user(request: Request, response: Response):
    if not request.is_json:
        return response.status(400).json({"error": "JSON content required"})
    
    try:
        json_data = await request.json
        user_data = UserCreateRequest(**json_data)
        
        # Create user with validated data
        user = await create_user_in_db(user_data)
        return response.status(201).json(user)
        
    except ValidationError as e:
        return response.status(400).json({"error": "Validation failed", "details": e.errors()})
    except json.JSONDecodeError:
        return response.status(400).json({"error": "Invalid JSON"})
```

### Conditional Processing

```python
async def api_handler(request: Request, response: Response):
    # Content negotiation
    if request.accepts_json:
        data = {"message": "Hello, World!"}
        return response.json(data)
    elif request.accepts_html:
        html = "<h1>Hello, World!</h1>"
        return response.html(html)
    else:
        return response.text("Hello, World!")
```

## ⚠️ Error Handling

### Connection Errors

```python
async def handler(request: Request, response: Response):
    try:
        # Check if client is still connected
        if await request.is_disconnected():
            return  # Client disconnected, stop processing
        
        # Process request
        data = await request.json
        
    except ClientDisconnect:
        # Handle client disconnection
        logger.info("Client disconnected during request processing")
        return
```

### Validation and Parsing Errors

```python
async def handler(request: Request, response: Response):
    try:
        if request.is_json:
            data = await request.json
        elif request.is_form:
            data = await request.form
        else:
            return response.status(400).json({"error": "Unsupported content type"})
            
    except json.JSONDecodeError:
        return response.status(400).json({"error": "Invalid JSON format"})
    except UnicodeDecodeError:
        return response.status(400).json({"error": "Invalid text encoding"})
    except Exception as e:
        logger.error(f"Request parsing error: {e}")
        return response.status(500).json({"error": "Internal server error"})
```

## ✨ Best Practices

1. **Always check content type** before parsing request body
2. **Use appropriate parsing method** (json, form, files) based on content type
3. **Validate input data** using Pydantic models or custom validation
4. **Handle client disconnections** for long-running operations
5. **Set reasonable limits** for file uploads and request sizes
6. **Use streaming** for large file uploads
7. **Check authentication state** before processing sensitive operations
8. **Log important request information** for debugging and monitoring

## 🔍 See Also

- [Response](./response.md) - HTTP response handling
- [Middleware](./middleware.md) - Request/response middleware