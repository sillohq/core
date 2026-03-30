# Nexios HTTP And Routing

Use this reference for day-to-day endpoint authoring in Nexios.

## Table of Contents

1. [Basic Handlers](#basic-handlers)
2. [Request Inputs](#request-inputs)
3. [Response Patterns](#response-patterns)
4. [Routing Decorators](#routing-decorators)
5. [Typed Path Parameters](#typed-path-parameters)
6. [Route and Router](#route-and-router)
7. [Class-Based Handlers](#class-based-handlers)
8. [File Uploads](#file-uploads)
9. [Pagination](#pagination)

## Basic Handlers

The most common Nexios shape is:

```python
from nexios import NexiosApp

app = NexiosApp()

@app.get("/health")
async def health(request, response):
    return response.json({"status": "ok"})
```

Use this pattern when teaching first principles.

## Request Inputs

### JSON Body

```python
@app.post("/users")
async def create_user(request, response):
    data = await request.json
    return response.json({"received": data}, status_code=201)
```

### Form Data

```python
@app.post("/submit-form")
async def submit_form(request, response):
    form = await request.form_data
    return response.json({"name": form.get("name")})
```

### Files

```python
@app.post("/upload")
async def upload(request, response):
    files = await request.files
    avatar = files.get("avatar")
    if not avatar:
        return response.status(400).json({"error": "Missing avatar"})
    content = await avatar.read()
    return response.json({"filename": avatar.filename, "size": len(content)})
```

### Streaming Request Data

```python
@app.post("/stream")
async def stream_input(request, response):
    body = b""
    async for chunk in request.stream():
        body += chunk
    return response.json({"bytes": len(body)})
```

## Response Patterns

Nexios can serialize simple return values, but for teaching clarity prefer the response object.

### JSON

```python
@app.get("/users")
async def list_users(request, response):
    return response.json([{"id": 1, "name": "Ada"}])
```

### Text, HTML, File, Redirect, Stream

```python
@app.get("/plain")
async def plain(request, response):
    return response.text("hello")

@app.get("/page")
async def page(request, response):
    return response.html("<h1>Hello</h1>")

@app.get("/download")
async def download(request, response):
    return response.file("report.pdf")

@app.get("/go-home")
async def go_home(request, response):
    return response.redirect("/")

@app.get("/stream")
async def stream_numbers(request, response):
    async def generator():
        for i in range(3):
            yield f"{i}\n"
    return response.stream(generator())
```

### Chaining Status, Headers, and Cookies

```python
@app.post("/login")
async def login(request, response):
    return (
        response
        .json({"ok": True})
        .set_cookie("session_id", "abc123", httponly=True, secure=True)
        .status(200)
    )
```

Important documented rule:

- Set the response type first with `.json()`, `.text()`, `.html()`, `.file()`, `.stream()`, `.redirect()`, or `.empty()` before using cookie or header helpers.
- Prefer the `response` object whenever the example needs status codes, cookies, headers, redirects, files, streaming, or pagination.

## Routing Decorators

The decorator API is the default way to teach Nexios routing:

```python
@app.get("/")
async def index(request, response):
    return response.json({"message": "Hello"})

@app.post("/items")
async def create_item(request, response):
    data = await request.json
    return response.json(data, status_code=201)

@app.put("/items/{item_id}")
async def update_item(request, response, item_id: str):
    data = await request.json
    return response.json({"id": item_id, **data})

@app.delete("/items/{item_id}")
async def delete_item(request, response, item_id: str):
    return response.json(None, status_code=204)
```

## Typed Path Parameters

Nexios documents typed parameters such as `int`, `float`, `uuid`, `path`, and `slug`.

Use direct handler arguments:

```python
@app.get("/users/{user_id:int}")
async def get_user(request, response, user_id: int):
    return response.json({"id": user_id})
```

Important teaching note:

- The docs explicitly warn that path parameters should be passed directly to handler arguments instead of relying on older `request.path_params` access patterns.

## Route and Router

Use `Route` when teaching explicit route objects:

```python
from nexios.routing import Route

async def get_user_handler(request, response, user_id: int):
    return response.json({"user_id": user_id})

app.add_route(Route(
    path="/users/{user_id:int}",
    handler=get_user_handler,
    methods=["GET"],
    name="get_user",
    summary="Get user by ID"
))
```

Use `Router` when teaching organization:

```python
from nexios.routing import Router

api = Router(prefix="/api", tags=["API"])

@api.get("/users")
async def list_users(request, response):
    return response.json([])

app.mount_router(api)
```

## Class-Based Handlers

Use class-based handlers when the user wants a structured, reusable endpoint surface:

```python
from nexios.views import APIHandler

class UserView(APIHandler):
    async def get(self, request, response):
        return response.json({"message": "user view"})

app.add_route(UserView.as_route("/user"))
```

This is useful when a group of HTTP methods belongs to one resource.

## File Uploads

Single-file example:

```python
@app.post("/upload-image")
async def upload_image(request, response):
    files = await request.files
    image = files.get("image")
    if not image:
        return response.status(400).json({"error": "No image uploaded"})

    if image.content_type not in {"image/jpeg", "image/png"}:
        return response.status(400).json({"error": "Unsupported type"})

    content = await image.read()
    return response.json({"filename": image.filename, "size": len(content)})
```

Teach these best practices:

- Validate extension and MIME type
- Do not trust original filenames
- Stream or chunk large files

## Pagination

The simplest example uses `response.paginate(...)`:

```python
@app.get("/items")
async def list_items(request, response):
    data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]
    return response.paginate(data)
```

Async variant:

```python
@app.get("/async-items")
async def list_async_items(request, response):
    data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]
    return response.apaginate(data)
```

Documented pagination strategies:

- `page_number`
- `limit_offset`
- `cursor`

Example with a custom strategy:

```python
from nexios.pagination import PageNumberPagination

@app.get("/products")
async def products(request, response):
    data = [{"id": i, "name": f"Product {i}"} for i in range(1, 51)]
    strategy = PageNumberPagination(default_page_size=10, max_page_size=50)
    return response.paginate(data, strategy=strategy)
```
