# TestClient

The `TestClient` class provides a convenient way to test Nexios applications by making HTTP requests without running a server. It extends `httpx.Client` and handles ASGI application lifecycle automatically.

## 📋 Class Definition

```python
class TestClient(httpx.Client):
    def __init__(
        self,
        app: ASGIApp,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        root_path: str = "",
        backend: Literal["asyncio", "trio"] = "asyncio",
        backend_options: dict[str, Any] | None = None,
        cookies: CookieTypes | None = None,
        headers: HeaderTypes | None = None,
        follow_redirects: bool = True,
        check_asgi_conformance: bool = True,
    )
```

## ⚙️ Constructor Parameters

### app: ASGIApp
**Type**: `ASGIApp`  
**Required**: Yes

The ASGI application to test.

```python
from nexios import NexiosApp
from nexios.testclient import TestClient

app = NexiosApp()

@app.get("/")
async def home(request, response):
    return response.json({"message": "Hello World"})

client = TestClient(app)
```

### base_url: str
**Type**: `str`  
**Default**: `"http://testserver"`

The base URL for all requests.

```python
client = TestClient(app, base_url="http://localhost:8000")
```

### raise_server_exceptions: bool
**Type**: `bool`  
**Default**: `True`

Whether to raise exceptions that occur in the application during testing.

```python
# Raise exceptions for debugging
client = TestClient(app, raise_server_exceptions=True)

# Suppress exceptions to test error responses
client = TestClient(app, raise_server_exceptions=False)
```

### root_path: str
**Type**: `str`  
**Default**: `""`

The root path for the application.

```python
client = TestClient(app, root_path="/api/v1")
```

### backend: Literal["asyncio", "trio"]
**Type**: `str`  
**Default**: `"asyncio"`

The async backend to use for running the application.

```python
# Use asyncio (default)
client = TestClient(app, backend="asyncio")

# Use trio
client = TestClient(app, backend="trio")
```

### backend_options: dict[str, Any] | None
**Type**: `dict`  
**Default**: `None`

Options for the async backend.

```python
client = TestClient(
    app,
    backend="asyncio",
    backend_options={"debug": True}
)
```

### cookies: CookieTypes | None
**Type**: `httpx.CookieTypes`  
**Default**: `None`

Default cookies to include with requests.

```python
client = TestClient(
    app,
    cookies={"session_id": "abc123"}
)
```

### headers: HeaderTypes | None
**Type**: `httpx.HeaderTypes`  
**Default**: `None`

Default headers to include with requests.

```python
client = TestClient(
    app,
    headers={"Authorization": "Bearer token123"}
)
```

### follow_redirects: bool
**Type**: `bool`  
**Default**: `True`

Whether to automatically follow redirects.

```python
client = TestClient(app, follow_redirects=False)
```

### check_asgi_conformance: bool
**Type**: `bool`  
**Default**: `True`

Whether to check ASGI protocol conformance.

```python
client = TestClient(app, check_asgi_conformance=False)
```

## 🌐 HTTP Methods

### get()
Make a GET request.

```python
def get(self, url: URLTypes, **kwargs: Any) -> httpx.Response
```

**Usage:**
```python
response = client.get("/users")
response = client.get("/users", params={"page": 1})
response = client.get("/users", headers={"Accept": "application/json"})
```

### post()
Make a POST request.

```python
def post(self, url: URLTypes, **kwargs: Any) -> httpx.Response
```

**Usage:**
```python
response = client.post("/users", json={"name": "John"})
response = client.post("/users", data={"name": "John"})
response = client.post("/upload", files={"file": open("test.txt", "rb")})
```

### put()
Make a PUT request.

```python
def put(self, url: URLTypes, **kwargs: Any) -> httpx.Response
```

**Usage:**
```python
response = client.put("/users/1", json={"name": "John Updated"})
```

### patch()
Make a PATCH request.

```python
def patch(self, url: URLTypes, **kwargs: Any) -> httpx.Response
```

**Usage:**
```python
response = client.patch("/users/1", json={"name": "John"})
```

### delete()
Make a DELETE request.

```python
def delete(self, url: URLTypes, **kwargs: Any) -> httpx.Response
```

**Usage:**
```python
response = client.delete("/users/1")
```

### head()
Make a HEAD request.

```python
def head(self, url: URLTypes, **kwargs: Any) -> httpx.Response
```

**Usage:**
```python
response = client.head("/users/1")
```

### options()
Make an OPTIONS request.

```python
def options(self, url: URLTypes, **kwargs: Any) -> httpx.Response
```

**Usage:**
```python
response = client.options("/users")
```

## 🔌 WebSocket Support

### websocket_connect()
Establish a WebSocket connection for testing.

```python
def websocket_connect(
    self,
    url: str,
    subprotocols: Sequence[str] | None = None,
    **kwargs: Any,
) -> WebSocketTestSession
```

**Usage:**
```python
with client.websocket_connect("/ws") as websocket:
    websocket.send_text("Hello")
    data = websocket.receive_text()
    assert data == "Hello"
```

## 🔄 Context Manager Support

### Synchronous Context Manager

```python
with TestClient(app) as client:
    response = client.get("/")
    assert response.status_code == 200
```

### Asynchronous Context Manager

```python
async with TestClient(app) as client:
    response = await client.get("/")
    assert response.status_code == 200
```

## 💡 Usage Examples

### Basic Testing

```python
from nexios import NexiosApp
from nexios.testclient import TestClient

app = NexiosApp()

@app.get("/")
async def home(request, response):
    return response.json({"message": "Hello World"})

@app.get("/users/{user_id}")
async def get_user(request, response):
    user_id = request.path_params["user_id"]
    return response.json({"id": user_id, "name": "John"})

# Test the application
client = TestClient(app)

def test_home():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}

def test_get_user():
    response = client.get("/users/123")
    assert response.status_code == 200
    assert response.json() == {"id": "123", "name": "John"}
```

### Testing with Authentication

```python
app = NexiosApp()

@app.get("/protected")
async def protected(request, response):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return response.status(401).json({"error": "Unauthorized"})
    return response.json({"message": "Protected data"})

client = TestClient(app)

def test_protected_without_auth():
    response = client.get("/protected")
    assert response.status_code == 401

def test_protected_with_auth():
    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer token123"}
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Protected data"}
```

### Testing POST Requests

```python
app = NexiosApp()

@app.post("/users")
async def create_user(request, response):
    user_data = await request.json
    user_data["id"] = 123
    return response.status(201).json(user_data)

client = TestClient(app)

def test_create_user():
    user_data = {"name": "John", "email": "john@example.com"}
    response = client.post("/users", json=user_data)
    
    assert response.status_code == 201
    result = response.json()
    assert result["id"] == 123
    assert result["name"] == "John"
    assert result["email"] == "john@example.com"
```

### Testing File Uploads

```python
app = NexiosApp()

@app.post("/upload")
async def upload_file(request, response):
    form = await request.form
    file = form.get("file")
    if file:
        content = await file.read()
        return response.json({
            "filename": file.filename,
            "size": len(content)
        })
    return response.status(400).json({"error": "No file"})

client = TestClient(app)

def test_file_upload():
    with open("test.txt", "w") as f:
        f.write("test content")
    
    with open("test.txt", "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("test.txt", f, "text/plain")}
        )
    
    assert response.status_code == 200
    result = response.json()
    assert result["filename"] == "test.txt"
    assert result["size"] == 12
```

### Testing with Cookies

```python
app = NexiosApp()

@app.get("/set-cookie")
async def set_cookie(request, response):
    response.set_cookie("session_id", "abc123")
    return response.json({"message": "Cookie set"})

@app.get("/get-cookie")
async def get_cookie(request, response):
    session_id = request.cookies.get("session_id")
    return response.json({"session_id": session_id})

client = TestClient(app)

def test_cookies():
    # Set cookie
    response = client.get("/set-cookie")
    assert response.status_code == 200
    
    # Cookie should be automatically included in subsequent requests
    response = client.get("/get-cookie")
    assert response.status_code == 200
    assert response.json() == {"session_id": "abc123"}
```

### Testing WebSocket Connections

```python
from nexios.websockets import WebSocket

app = NexiosApp()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Echo: {data}")

client = TestClient(app)

def test_websocket():
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("Hello")
        data = websocket.receive_text()
        assert data == "Echo: Hello"
        
        websocket.send_text("World")
        data = websocket.receive_text()
        assert data == "Echo: World"
```

### Testing Error Handling

```python
app = NexiosApp()

@app.get("/error")
async def error_endpoint(request, response):
    raise ValueError("Something went wrong")

# Test with exceptions raised
client = TestClient(app, raise_server_exceptions=True)

def test_error_with_exceptions():
    try:
        client.get("/error")
        assert False, "Should have raised an exception"
    except ValueError as e:
        assert str(e) == "Something went wrong"

# Test with exceptions suppressed
client_no_raise = TestClient(app, raise_server_exceptions=False)

def test_error_without_exceptions():
    response = client_no_raise.get("/error")
    assert response.status_code == 500
```

### Testing with Custom Headers

```python
app = NexiosApp()

@app.get("/api-version")
async def api_version(request, response):
    version = request.headers.get("X-API-Version", "v1")
    return response.json({"version": version})

client = TestClient(app)

def test_custom_headers():
    # Default version
    response = client.get("/api-version")
    assert response.json() == {"version": "v1"}
    
    # Custom version
    response = client.get(
        "/api-version",
        headers={"X-API-Version": "v2"}
    )
    assert response.json() == {"version": "v2"}
```

### Testing with Query Parameters

```python
app = NexiosApp()

@app.get("/search")
async def search(request, response):
    query = request.query_params.get("q", "")
    limit = int(request.query_params.get("limit", "10"))
    
    return response.json({
        "query": query,
        "limit": limit,
        "results": []
    })

client = TestClient(app)

def test_query_parameters():
    response = client.get("/search", params={"q": "python", "limit": "5"})
    
    assert response.status_code == 200
    result = response.json()
    assert result["query"] == "python"
    assert result["limit"] == 5
```

### Async Testing

```python
import pytest

app = NexiosApp()

@app.get("/async-data")
async def async_data(request, response):
    # Simulate async operation
    await asyncio.sleep(0.1)
    return response.json({"data": "async result"})

@pytest.mark.asyncio
async def test_async_client():
    async with TestClient(app) as client:
        response = await client.get("/async-data")
        assert response.status_code == 200
        assert response.json() == {"data": "async result"}
```

## 📊 Properties

### app: ASGIApp
The ASGI application being tested.

```python
client = TestClient(app)
assert client.app is app
```

### base_url: str
The base URL for requests.

```python
client = TestClient(app, base_url="http://localhost:8000")
assert str(client.base_url) == "http://localhost:8000"
```

## 🔍 See Also

- [NexiosApp](./nexios-app.md) - Main application class
- [Request](./request.md) - HTTP request handling
- [Response](./response.md) - HTTP response creation
- [WebSocket](./websocket.md) - WebSocket connections