---
title: Request Information in sillo
description: sillo provides a comprehensive `Request` object that gives you access to all the information about the incoming HTTP request. This object is automatically passed to your route handlers and
  contains methods and properties to access request data.
head:
- tag: meta
  attrs:
    property: og:title
    content: Request Information in sillo
- tag: meta
  attrs:
    property: og:description
    content: sillo provides a comprehensive `Request` object that gives you access to all the information about the incoming HTTP request. This object is automatically passed to your route handlers and
      contains methods and properties to access request data.
---
#  Request Information

```python
@app.get("/example")
async def example_handler(request: Request, response):
    # Basic request information
    method = request.method        # HTTP method (GET, POST, etc.)
    url = request.url              # Full URL object
    path = request.path            # Request path (/example)
    headers = request.headers      # Headers dictionary
    client_ip = request.client     # Client address (IP, port)
```

##  Query Parameters

Access URL query parameters (after the `?` in the URL):

```python
@app.get("/search")
async def search_handler(request: Request, response):
    # For URL: /search?q=sillo&page=2
    query = request.query_params.get("q")       # "sillo"
    page = request.query_params.get("page")     # "2"
    all_params = dict(request.query_params)    # {'q': 'sillo', 'page': '2'}
```

##  Path Parameters

Access named parameters from the route path:

```python
@app.get("/users/{user_id}")
async def user_handler(request: Request, response):
    # For URL: /users/123
    user_id = request.path_params["user_id"]  # "123"
    # Or directly as function parameter (shown above)
```

##  Request Body

### JSON Data

```python
@app.post("/data")
async def data_handler(request: Request, response):
    json_data = await request.json  # Parses JSON body
```

### Form Data

```python
@app.post("/submit")
async def submit_handler(request: Request, response):
    form_data = await request.form  # Parses both URL-encoded and multipart forms
    username = form_data.get("username")
```

### File Uploads

```python
@app.post("/upload")
async def upload_handler(request: Request, response):
    files = await request.files      # Dictionary of uploaded files
    file = files.get("document") # Access specific file
    if file:
        filename = file.filename
        content = await file.read()
```

### Raw Body

```python
@app.post("/raw")
async def raw_handler(request: Request, response):
    body_bytes = await request.body  # Raw bytes
    body_text = await request.text  # Decoded text
```

##  Cookies

```python
@app.get("/profile")
async def profile_handler(request: Request, response):
    session_id = request.cookies.get("session_id")
```

##  Client Information

```python
@app.get("/client-info")
async def client_info_handler(request: Request, response):
    user_agent = request.user_agent
    client_ip = request.client.host if request.client else None
    origin = request.origin
```

##  State and Middleware Data

```python
@app.get("/auth")
async def auth_handler(request: Request, response):
    # Access data added by middleware
    user = request.user
    session = request.session  # Requires session middleware
    custom_data = request.state.get("custom_data")
```

##  URL Construction

```python
@app.get("/links")
async def links_handler(request: Request, response):
    absolute_url = request.build_absolute_uri("/api/resource")
    # Returns full URL like "https://example.com/api/resource"
```


##  Request Type Detection

sillo provides convenient properties to quickly check the type and characteristics of incoming requests:

### Content Type Flags

```python
@app.post("/api/endpoint")
async def handle_request(request: Request, response):
    # Check content type
    if request.is_json:
        data = await request.json
        # Handle JSON data
    elif request.is_form:
        data = await request.form
        # Handle form data
    elif request.is_multipart:
        files = await request.files
        # Handle file uploads
    elif request.is_urlencoded:
        data = await request.form
        # Handle URL-encoded form data
```

### Request State Flags

```python
@app.post("/process")
async def process_request(request: Request, response):
    # Check if request has various components
    if request.has_cookie:
        session_id = request.cookies.get("session")

    if request.has_files:
        files = await request.files
        # Process uploaded files

    if request.has_body:
        # Request contains body data
        if request.content_length > 1000000:  # 1MB
            return response.status(413).text("File too large")

    if request.is_authenticated:
        user_id = request.user.id
        # Handle authenticated request

    if request.has_session:
        session_data = request.session
        # Access session data
```

### Request Type Properties

| Property | Description | Example |
|----------|-------------|---------|
| `request.is_json` | True if Content-Type is `application/json` | JSON API requests |
| `request.is_form` | True if Content-Type is form data (URL-encoded or multipart) | HTML forms |
| `request.is_multipart` | True if Content-Type is `multipart/form-data` | File uploads |
| `request.is_urlencoded` | True if Content-Type is `application/x-www-form-urlencoded` | Simple forms |
| `request.has_cookie` | True if request contains cookies | Session management |
| `request.has_files` | True if request contains uploaded files | File upload detection |
| `request.has_body` | True if request has a body | POST/PUT/PATCH requests |
| `request.is_authenticated` | True if user is authenticated | Authenticated requests |
| `request.has_session` | True if session middleware is available | Session-enabled requests |

### Existing Request Flags

sillo also provides additional request detection properties:

```python
@app.get("/responsive")
async def responsive_handler(request: Request, response):
    # Check request characteristics
    if request.is_ajax:
        return response.json({"message": "AJAX request"})

    if request.is_secure:
        return response.json({"protocol": "HTTPS"})

    if request.accepts_json:
        return response.json({"format": "JSON preferred"})

    if request.accepts_html:
        return response.html("<h1>HTML Response</h1>")
```

### Header Utilities

```python
@app.get("/headers")
async def header_handler(request: Request, response):
    # Check for specific headers
    if request.has_header("authorization"):
        token = request.get_header("authorization")

    # Get header with default value
    api_version = request.get_header("x-api-version", "v1")

    # Check if header exists
    if request.has_header("x-custom-header"):
        custom_value = request.get_header("x-custom-header")
```

| Method/Property | Description | Example |
|----------------|-------------|---------|
| `request.has_header(name)` | Check if header exists (case-insensitive) | `request.has_header("content-type")` |
| `request.get_header(name, default)` | Get header value with default | `request.get_header("x-api-key", "none")` |
| `request.is_ajax` | True if X-Requested-With is XMLHttpRequest | AJAX requests |
| `request.is_secure` | True if request uses HTTPS | Secure connections |
| `request.accepts_json` | True if client accepts JSON | API responses |
| `request.accepts_html` | True if client accepts HTML | Web page responses |

##  Advanced Features

### Streaming Requests

For handling large uploads:

```python
@app.post("/stream")
async def stream_handler(request: Request, response):
    async for chunk in request.stream:
        # Process each chunk of the request body
        process_chunk(chunk)
```

### Server Push

```python
@app.get("/push")
async def push_handler(request: Request, response):
    await request.send_push_promise("/static/style.css")
```

The sillo `Request` object provides a rich interface for working with incoming HTTP requests, with support for all common web standards and convenient access to request data. 