---
title: Handlers
description: Handlers are the heart of your Nexios application. They define how your application responds to incoming HTTP requests. Every route in your application is handled by a handler function that processes the request and returns a response.
head:
  - - meta
    - property: og:title
      content: Handlers
  - - meta
    - property: og:description
      content: Handlers are the heart of your Nexios application. They define how your application responds to incoming HTTP requests. Every route in your application is handled by a handler function that processes the request and returns a response.
---


# 🎯 Handlers
Handlers are the heart of your Nexios application. They define how your application responds to incoming HTTP requests. Every route in your application is handled by a handler function that processes the request and returns a response.

```python
from nexios import NexiosApp

app = NexiosApp()

@app.get("/")  
async def index(request, response): 
    return "Hello, world!" 
```

::: tip
Nexios handler most accept at least two parameters
:::


## 📋 Handler Basics

## 🏗️ Type Annotations for Better Development Experience

Using type annotations provides better IDE support, improved documentation, static type checking, better refactoring support, and clearer interfaces between components.

```python
from nexios.http import Request, Response

@app.get("/")  
async def index(request: Request, response: Response): 
    return "Hello, world!" 
```

For more detailed information about request and response objects, see the Request and Response documentation.

## 🔧 Alternative Handler Registration

You can also register handlers using the `Route` class for more control over route configuration:

```python
from nexios.routing import Route
from nexios import NexiosApp

app = NexiosApp()

async def dynamic_handler(req, res):
    return "Hello, world!"

app.add_route(Route("/dynamic", dynamic_handler))  # Handles All Methods by default
```

## 🛣️ Handlers with path params
As seen at [`Dynamic Routing`](/guide/routing#dynamic-route) a nexios handler can optionally take an extra argument when a the route definition contains a dynamic value

```py
from nexios import NexiosApp

app = NexiosApp()

@app.get("/users/{user_id}")
async def get_user(request, response, user_id):
    return {"id": user_id}
```


## 📥 Request Processing

### Accessing Request Information

Handlers have access to comprehensive request information through the request object:

```python
@app.post("/upload")
async def upload_file(request, response):
    # Request method
    method = request.method  # "POST"
    
    # URL information
    url = request.url  # Full URL
    path = request.path  # Path component
    query = request.query  # Query string
    
    # Headers
    content_type = request.headers.get("content-type")
    user_agent = request.headers.get("user-agent")
    
    # Client information
    client_ip = request.client.host
    client_port = request.client.port
    
    # Request body
    body = await request.body  # Raw bytes
    json_data = await request.json  # Parsed JSON
    form_data = await request.form  # Form data
    
    return response.json({
        "method": method,
        "path": path,
        "content_type": content_type,
        "client_ip": client_ip
    })
```


### 📊 Query Parameters

Query parameters are accessed through the `query_params` attribute:

```python
@app.get("/search")
async def search(request, response):
    # Get single parameter with default
    query = request.query_params.get("q", "")
    
    # Get parameter with type conversion
    page = int(request.query_params.get("page", 1))
    limit = int(request.query_params.get("limit", 10))
    
    # Get multiple values for the same parameter
    tags = request.query_params.getlist("tag")
    
    # Get all query parameters as dict
    all_params = dict(request.query_params)
    
    return response.json({
        "query": query,
        "page": page,
        "limit": limit,
        "tags": tags,
        "all_params": all_params
    })
```

### 📦 Request Body

Handlers can access the request body in various formats:

```python
@app.post("/data")
async def process_data(request, response):
    # JSON data
    json_data = await request.json
    
    # Form data
    form_data = await request.form
    
    # Raw bytes
    raw_body = await request.body
    
    # Text content
    text_content = await request.text
    
    return response.json({
        "json": json_data,
        "form": dict(form_data),
        "body_size": len(raw_body)
    })
```

## 📤 Response Handling

### 🎨 Creating Responses

Nexios provides multiple ways to create responses:

```python
@app.get("/responses")
async def demonstrate_responses(request, response):
    # JSON response
    return response.json({
        "message": "Hello",
        "status": "success"
    })
    
    # Text response
    return response.text("Hello, World!")
    
    # HTML response
    return response.html("<h1>Hello</h1>")
    
    # File response
    return response.file("path/to/file.pdf")
    
    # Redirect
    return response.redirect("/new-location")
    
    # Custom status code
    return response.json({"error": "Not found"}, status_code=404)
```

### 📋 Setting Headers

You can set custom headers on responses:

```python
@app.get("/custom-headers")
async def custom_headers(request, response):
    response.set_header("X-Custom-Header", "Custom Value")
    response.set_header("Cache-Control", "no-cache")
    response.set_header("Content-Type", "application/json")
    
    return response.json({"message": "Headers set"})
```

### 📊 Response Status Codes

Nexios provides convenient methods for common status codes:

```python
@app.get("/status-examples")
async def status_examples(request, response):
    # Success responses
    return response.json({"data": "success"}, status_code=200)
    return response.json({"created": True}, status_code=201)
    return response.json(None, status_code=204)
    
    # Client error responses
    return response.json({"error": "Bad request"}, status_code=400)
    return response.json({"error": "Unauthorized"}, status_code=401)
    return response.json({"error": "Forbidden"}, status_code=403)
    return response.json({"error": "Not found"}, status_code=404)
    
    # Server error responses
    return response.json({"error": "Internal error"}, status_code=500)
    return response.json({"error": "Service unavailable"}, status_code=503)
```

## ⚠️ Error Handling

### 🚨 Raising Exceptions

Handlers can raise exceptions that will be caught by exception handlers:

```python
from nexios.exceptions import HTTPException

@app.get("/users/{user_id:int}")
async def get_user(request, response):
    user_id = request.path_params.user_id
    
    # Simulate user not found
    if user_id > 1000:
        raise HTTPException(404, f"User {user_id} not found")
    
    # Simulate server error
    if user_id == 0:
        raise HTTPException(500, "Internal server error")
    
    return response.json({"id": user_id, "name": "John Doe"})
```

### 🛠️ Custom Exception Handling

You can define custom exception handlers:

```python
@app.add_exception_handler(ValueError)
async def handle_value_error(request, response, exc):
    return response.json({
        "error": "Invalid value provided",
        "details": str(exc)
    }, status_code=400)

@app.add_exception_handler(404)
async def handle_not_found(request, response, exc):
    return response.json({
        "error": "Resource not found",
        "path": request.path
    }, status_code=404)
```

## 💉 Dependency Injection

### 🎯 Using Dependencies

Handlers can use dependency injection for clean, testable code:

```python
from nexios.dependencies import Depend,Context

async def get_database():
    # This could return a database connection
    return {"connection": "active"}

async def get_current_user(request: Context().request, db=Depend(get_database)):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(401, "Unauthorized")
    
    # Use the database connection
    user = await db.get_user_by_token(token)
    return user

@app.get("/profile")
async def get_profile(request, response, user=Depend(get_current_user)):
    return response.json({
        "id": user.id,
        "name": user.name,
        "email": user.email
    })
```

### 🔄 Dependency Scopes

Dependencies can have different scopes:

```python
# Application-scoped dependency (shared across all requests)
async def get_config():
    return load_configuration()

# Request-scoped dependency (new instance per request)
async def get_db_connection():
    return await create_db_connection()

@app.get("/data")
async def get_data(
    request, 
    response, 
    config=Depend(get_config, scope="application"),
    db=Depend(get_db_connection, scope="request")
):
    # config is shared across all requests
    # db is a new connection for each request
    return response.json(await db.query("SELECT * FROM data"))
```

