---
title: Request Information in Nexios 
description: Nexios provides a comprehensive `Request` object that gives you access to all the information about the incoming HTTP request. This object is automatically passed to your route handlers and contains methods and properties to access request data.
head:
  - - meta
    - property: og:title
      content: Request Information in Nexios 
  - - meta
    - property: og:description
      content: Nexios provides a comprehensive `Request` object that gives you access to all the information about the incoming HTTP request. This object is automatically passed to your route handlers and contains methods and properties to access request data.
---
# 📥 Request Information

```python
@app.get("/example")
async def example_handler(req: Request, res):
    # Basic request information
    method = req.method        # HTTP method (GET, POST, etc.)
    url = req.url              # Full URL object
    path = req.path            # Request path (/example)
    headers = req.headers      # Headers dictionary
    client_ip = req.client     # Client address (IP, port)
```

## ❓ Query Parameters

Access URL query parameters (after the `?` in the URL):

```python
@app.get("/search")
async def search_handler(req: Request, res):
    # For URL: /search?q=nexios&page=2
    query = req.query_params.get("q")       # "nexios"
    page = req.query_params.get("page")     # "2"
    all_params = dict(req.query_params)    # {'q': 'nexios', 'page': '2'}
```

## 🛣️ Path Parameters

Access named parameters from the route path:

```python
@app.get("/users/{user_id}")
async def user_handler(req: Request, res):
    # For URL: /users/123
    user_id = req.path_params["user_id"]  # "123"
    # Or directly as function parameter (shown above)
```

## 📦 Request Body

### JSON Data

```python
@app.post("/data")
async def data_handler(req: Request, res):
    json_data = await req.json  # Parses JSON body
```

### Form Data

```python
@app.post("/submit")
async def submit_handler(req: Request, res):
    form_data = await req.form  # Parses both URL-encoded and multipart forms
    username = form_data.get("username")
```

### File Uploads

```python
@app.post("/upload")
async def upload_handler(req: Request, res):
    files = await req.files      # Dictionary of uploaded files
    file = files.get("document") # Access specific file
    if file:
        filename = file.filename
        content = await file.read()
```

### Raw Body

```python
@app.post("/raw")
async def raw_handler(req: Request, res):
    body_bytes = await req.body  # Raw bytes
    body_text = await req.text  # Decoded text
```

## 🍪 Cookies

```python
@app.get("/profile")
async def profile_handler(req: Request, res):
    session_id = req.cookies.get("session_id")
```

## 💻 Client Information

```python
@app.get("/client-info")
async def client_info_handler(req: Request, res):
    user_agent = req.user_agent
    client_ip = req.client.host if req.client else None
    origin = req.origin
```

## 📊 State and Middleware Data

```python
@app.get("/auth")
async def auth_handler(req: Request, res):
    # Access data added by middleware
    user = req.user
    session = req.session  # Requires session middleware
    custom_data = req.state.get("custom_data")
```

## 🔗 URL Construction

```python
@app.get("/links")
async def links_handler(req: Request, res):
    absolute_url = req.build_absolute_uri("/api/resource")
    # Returns full URL like "https://example.com/api/resource"
```


## 🔍 Request Type Detection

Nexios provides convenient properties to quickly check the type and characteristics of incoming requests:

### Content Type Flags

```python
@app.post("/api/endpoint")
async def handle_request(req: Request, res):
    # Check content type
    if req.is_json:
        data = await req.json
        # Handle JSON data
    elif req.is_form:
        data = await req.form()
        # Handle form data
    elif req.is_multipart:
        files = await req.files()
        # Handle file uploads
    elif req.is_urlencoded:
        data = await req.form()
        # Handle URL-encoded form data
```

### Request State Flags

```python
@app.post("/process")
async def process_request(req: Request, res):
    # Check if request has various components
    if req.has_cookie:
        session_id = req.cookies.get("session")

    if req.has_files:
        files = await req.files()
        # Process uploaded files

    if req.has_body:
        # Request contains body data
        if req.content_length > 1000000:  # 1MB
            return res.status(413).text("File too large")

    if req.is_authenticated:
        user_id = req.user.id
        # Handle authenticated request

    if req.has_session:
        session_data = req.session
        # Access session data
```

### Request Type Properties

| Property | Description | Example |
|----------|-------------|---------|
| `req.is_json` | True if Content-Type is `application/json` | JSON API requests |
| `req.is_form` | True if Content-Type is form data (URL-encoded or multipart) | HTML forms |
| `req.is_multipart` | True if Content-Type is `multipart/form-data` | File uploads |
| `req.is_urlencoded` | True if Content-Type is `application/x-www-form-urlencoded` | Simple forms |
| `req.has_cookie` | True if request contains cookies | Session management |
| `req.has_files` | True if request contains uploaded files | File upload detection |
| `req.has_body` | True if request has a body | POST/PUT/PATCH requests |
| `req.is_authenticated` | True if user is authenticated | Authenticated requests |
| `req.has_session` | True if session middleware is available | Session-enabled requests |

### Existing Request Flags

Nexios also provides additional request detection properties:

```python
@app.get("/responsive")
async def responsive_handler(req: Request, res):
    # Check request characteristics
    if req.is_ajax:
        return res.json({"message": "AJAX request"})

    if req.is_secure:
        return res.json({"protocol": "HTTPS"})

    if req.accepts_json:
        return res.json({"format": "JSON preferred"})

    if req.accepts_html:
        return res.html("<h1>HTML Response</h1>")
```

### Header Utilities

```python
@app.get("/headers")
async def header_handler(req: Request, res):
    # Check for specific headers
    if req.has_header("authorization"):
        token = req.get_header("authorization")

    # Get header with default value
    api_version = req.get_header("x-api-version", "v1")

    # Check if header exists
    if req.has_header("x-custom-header"):
        custom_value = req.get_header("x-custom-header")
```

| Method/Property | Description | Example |
|----------------|-------------|---------|
| `req.has_header(name)` | Check if header exists (case-insensitive) | `req.has_header("content-type")` |
| `req.get_header(name, default)` | Get header value with default | `req.get_header("x-api-key", "none")` |
| `req.is_ajax` | True if X-Requested-With is XMLHttpRequest | AJAX requests |
| `req.is_secure` | True if request uses HTTPS | Secure connections |
| `req.accepts_json` | True if client accepts JSON | API responses |
| `req.accepts_html` | True if client accepts HTML | Web page responses |

## ⚡ Advanced Features

### Streaming Requests

For handling large uploads:

```python
@app.post("/stream")
async def stream_handler(req: Request, res):
    async for chunk in req.stream():
        # Process each chunk of the request body
        process_chunk(chunk)
```

### Server Push

```python
@app.get("/push")
async def push_handler(req: Request, res):
    await req.send_push_promise("/static/style.css")
```

The Nexios `Request` object provides a rich interface for working with incoming HTTP requests, with support for all common web standards and convenient access to request data. 