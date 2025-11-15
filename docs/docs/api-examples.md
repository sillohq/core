---
outline: deep
---

# Nexios API Examples

This guide provides canonical, working examples for building APIs with Nexios. All code is idiomatic and matches the Nexios source, docs, and real-world examples.

::: tip Nexios Request API
- Use `await req.json` (not `req.json()`)
- Use `await req.files` (not `req.files()`)
- Use `req.path_params.param` (not `req.path_params['param']`)
:::

## 1. Minimal App and REST API

```python
from nexios import NexiosApp

app = NexiosApp()

@app.get("/api/items")
async def get_items(req, res):
    items = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
    return res.json(items)

@app.get("/api/items/{item_id:int}")
async def get_item(req, res):
    item_id = req.path_params.item_id
    return res.json({"id": item_id, "name": f"Item {item_id}"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)
```

## 2. Request Input Handling (JSON Body)

```python
from pydantic import BaseModel, ValidationError
from nexios import NexiosApp

app = NexiosApp()

class User(BaseModel):
    name: str
    age: int

@app.post("/json")
async def process_json(req, res):
    try:
        data = await req.json
        user = User(**data)
        return res.json({"status": "success", "user": user.dict()})
    except ValidationError as e:
        return res.json({"error": str(e)}, status_code=422)
```

## 2.5. Request Type Detection and Smart Handling

Nexios provides convenient properties to quickly detect and handle different types of requests:

```python
from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()

@app.post("/api/smart-endpoint")
async def smart_handler(req: Request, res: Response):
    """Smart endpoint that handles multiple input types"""

    # Check content type and handle accordingly
    if req.is_json:
        data = await req.json
        return res.json({
            "type": "json",
            "data": data,
            "content_type": req.content_type
        })

    elif req.is_form:
        if req.is_multipart:
            # Handle file uploads
            files = await req.files()
            form_data = await req.form()
            return res.json({
                "type": "multipart",
                "files": list(files.keys()),
                "form_fields": dict(form_data),
                "content_type": req.content_type
            })
        else:
            # Handle URL-encoded form
            form_data = await req.form()
            return res.json({
                "type": "urlencoded",
                "data": dict(form_data),
                "content_type": req.content_type
            })

    elif req.has_body:
        # Handle other content types
        body_text = await req.text()
        return res.json({
            "type": "raw",
            "content_type": req.content_type,
            "size": len(body_text)
        })

    else:
        return res.json({"error": "No body provided"}, status_code=400)

@app.get("/api/request-info")
async def request_info(req: Request, res: Response):
    """Get comprehensive information about the current request"""

    info = {
        "method": req.method,
        "path": req.path,
        "content_type": req.content_type,
        "content_length": req.content_length,

        # Content type flags
        "is_json": req.is_json,
        "is_form": req.is_form,
        "is_multipart": req.is_multipart,
        "is_urlencoded": req.is_urlencoded,

        # Request state flags
        "has_cookie": req.has_cookie,
        "has_files": req.has_files,
        "has_body": req.has_body,
        "is_authenticated": req.is_authenticated,
        "has_session": req.has_session,

        # Security and client info
        "is_secure": req.is_secure,
        "is_ajax": req.is_ajax,
        "client_ip": req.get_client_ip(),
        "user_agent": req.user_agent,

        # Headers (using new utilities)
        "has_authorization": req.has_header("authorization"),
        "accept_header": req.get_header("accept"),
    }

    return res.json(info)

@app.post("/api/validate-input")
async def validate_input(req: Request, res: Response):
    """Validate and process different input types"""

    # File size validation
    if req.has_body and req.content_length > 10 * 1024 * 1024:  # 10MB
        return res.json({"error": "File too large"}, status_code=413)

    # Authentication check
    if req.is_authenticated:
        user_info = {
            "id": req.user.id if req.user else None,
            "authenticated": True
        }
    else:
        user_info = {"authenticated": False}

    # Content type specific processing
    if req.is_json:
        data = await req.json(
        return res.json({
            "processed": True,
            "input_type": "json",
            "user": user_info,
            "data": data
        })

    elif req.is_multipart and req.has_files:
        files = await req.files()
        return res.json({
            "processed": True,
            "input_type": "multipart",
            "user": user_info,
            "files_count": len(files),
            "files": [f.filename for f in files.values()]
        })

    elif req.is_form:
        form_data = await req.form_data
        return res.json({
            "processed": True,
            "input_type": "form",
            "user": user_info,
            "fields": list(form_data.keys())
        })

    else:
        return res.json({
            "error": "Unsupported content type",
            "supported_types": ["application/json", "multipart/form-data", "application/x-www-form-urlencoded"]
        }, status_code=400)
```

## 3. Header Management and Custom Headers

```python
from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()

@app.get("/api/headers")
async def header_demo(req: Request, res: Response):
    """Demonstrate header utilities"""

    # Check for specific headers
    if req.has_header("authorization"):
        auth_type = "Bearer" if "Bearer" in req.get_header("authorization", "") else "Other"
        return res.json({
            "authenticated": True,
            "auth_type": auth_type,
            "api_version": req.get_header("x-api-version", "v1")
        })

    # Check for API key
    api_key = req.get_header("x-api-key")
    if not api_key:
        return res.json({"error": "API key required"}, status_code=401)

    # Check client preferences
    if req.accepts_json:
        format = "json"
    elif req.accepts_html:
        format = "html"
    else:
        format = "text"

    return res.json({
        "api_key_provided": bool(api_key),
        "preferred_format": format,
        "is_ajax": req.is_ajax,
        "user_agent": req.user_agent
    })
```

## 4. File Upload and Download

```python
from nexios import NexiosApp
from pathlib import Path

app = NexiosApp()
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.post("/upload")
async def upload_files(req, res):
    files = await req.files
    uploaded = []
    for name, file in files.items():
        # Read file content for processing/saving
        file_content = await file.read()
        file_path = UPLOAD_DIR / file.filename
        
        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        uploaded.append({
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(file_content),
            "saved_path": str(file_path)
        })
    return res.json({"uploaded": uploaded})

@app.get("/files/{filename}")
async def download_file(req, res):
    filename = req.path_params.filename
    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        return res.json({"error": "File not found"}, status_code=404)
    from nexios.responses import FileResponse
    return FileResponse(filepath, filename=filename)

```
## 5. Authentication (Session and JWT)

### Session Auth Example
```python
from nexios import NexiosApp
from nexios.auth.backends.session import SessionAuthBackend
from nexios.auth.middleware import AuthenticationMiddleware
from nexios.auth.base import BaseUser

class User(BaseUser):
    def __init__(self, id: str, username: str):
        self.id = id
        self.username = username

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def identity(self) -> str:
        return self.id

    @property
    def display_name(self) -> str:
        return self.username

    @classmethod
    async def load_user(cls, identity: str):
        # Replace with your database lookup
        user_data = get_user_from_db(identity)
        if user_data:
            return cls(id=user_data["id"], username=user_data["username"])
        return None

app = NexiosApp()

# Session backend
session_backend = SessionAuthBackend()

app.add_middleware(AuthenticationMiddleware(
    user_model=User,
    backend=session_backend
))

@app.get("/protected")
async def protected(req, res):
    if req.user and req.user.is_authenticated:
        return res.json({"message": f"Hello, {req.user.display_name}!"})
    return res.json({"error": "Not authenticated"}, status_code=401)

@app.post("/login")
async def login(req, res):
    data = await req.json
    username = data.get("username")
    password = data.get("password")

    # Validate credentials (replace with your logic)
    if username == "admin" and password == "password":
        user = User(id="123", username=username)
        from nexios.auth.backends.session import login
        login(req, user)
        return res.json({"message": "Logged in successfully"})

    return res.json({"error": "Invalid credentials"}, status_code=401)
```

### JWT Auth Example
```python
from nexios import NexiosApp
from nexios.auth.backends.jwt import JWTAuthBackend, create_jwt
from nexios.auth.middleware import AuthenticationMiddleware
from nexios.auth.base import BaseUser

class User(BaseUser):
    def __init__(self, id: str, username: str):
        self.id = id
        self.username = username

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def identity(self) -> str:
        return self.id

    @property
    def display_name(self) -> str:
        return self.username

    @classmethod
    async def load_user(cls, identity: str):
        # Replace with your database lookup
        user_data = get_user_from_db(identity)
        if user_data:
            return cls(id=user_data["id"], username=user_data["username"])
        return None

app = NexiosApp()

# JWT backend
jwt_backend = JWTAuthBackend()

app.add_middleware(AuthenticationMiddleware(
    user_model=User,
    backend=jwt_backend
))

@app.post("/login")
async def login(req, res):
    data = await req.json
    username = data.get("username")
    password = data.get("password")

    # Validate credentials (replace with your logic)
    if username == "admin" and password == "password":
        user = User(id="123", username=username)
        token = create_jwt({"sub": user.identity})
        return res.json({"token": token})

    return res.json({"error": "Invalid credentials"}, status_code=401)

@app.get("/protected")
async def protected(req, res):
    if req.user and req.user.is_authenticated:
        return res.json({"message": f"Hello, {req.user.display_name}!"})
    return res.json({"error": "Not authenticated"}, status_code=401)
```

## 6. Middleware Usage


### Custom Middleware
```python
async def custom_middleware(req, res,call_next):
    print("Custom middleware called")
    return await call_next(req, res)
app.add_middleware(custom_middleware)
```
### Class Based Middleware
```py
from nexios import BaseMiddleware

class CustomMiddleware(BaseMiddleware):
    async def process_request(self, req, res,call_next):
        print("Custom middleware called")
        return await call_next(req, res)
app.add_middleware(CustomMiddleware())
```
### Inbuilt Middleware
```python
from nexios import NexiosApp
from nexios.middleware import CORSMiddleware, SecurityMiddleware

app = NexiosApp()
app.add_middleware(CORSMiddleware())
app.add_middleware(SecurityMiddleware())
```

## 7. Error Handling

```python
from nexios import NexiosApp
from nexios.exceptions import HTTPException

app = NexiosApp()

@app.get("/error")
async def error_route(req, res):
    raise HTTPException(400, "This is a bad request!")

@app.add_exception_handler(HTTPException)
async def handle_http_exception(req, res, exc):
    return res.json({"error": exc.detail}, status_code=exc.status_code)
```

## 8. WebSockets (Minimal)

```python
from nexios import NexiosApp
from nexios.websockets import WebSocket

app = NexiosApp()

@app.ws_route("/ws")
async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_text(f"Echo: {message}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()
```

## 9. WebSockets (Chat Room)

```python
from typing import Dict, Set
from nexios import NexiosApp
from nexios.websockets import WebSocket

app = NexiosApp()
chat_rooms: Dict[str, Set[WebSocket]] = {}

@app.ws_route("/ws/chat/{room_id}")
async def chat_room(websocket: WebSocket):
    room_id = websocket.path_params.room_id
    await websocket.accept()
    if room_id not in chat_rooms:
        chat_rooms[room_id] = set()
    chat_rooms[room_id].add(websocket)
    try:
        for client in chat_rooms[room_id]:
            if client != websocket:
                await client.send_json({"type": "system", "message": "New user joined the chat"})
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            for client in chat_rooms[room_id]:
                if client != websocket:
                    await client.send_json({"type": "message", "message": message})
    except Exception as e:
        print(f"WebSocket error in room {room_id}: {e}")
    finally:
        chat_rooms[room_id].remove(websocket)
        if not chat_rooms[room_id]:
            del chat_rooms[room_id]
        await websocket.close()
```

## 10. Advanced Validation (Pydantic, Enums, Query Params)

```python
from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ValidationError, constr
from nexios import NexiosApp

app = NexiosApp()

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=50)
    email: EmailStr
    password: constr(min_length=8)
    full_name: str
    birth_date: Optional[date] = None
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE

@app.post("/users")
async def create_user(request, response):
    try:
        data = await request.json
        user = UserCreate(**data)
        return response.json(user.dict())
    except ValidationError as e:
        return response.json({"error": str(e)}, status_code=422)

class PaginationParams(BaseModel):
    page: int = Field(ge=1, default=1)
    limit: int = Field(ge=1, le=100, default=10)
    sort_by: str = Field(default="created_at")
    order: str = Field(default="desc")

@app.get("/users")
async def list_users(request, response):
    try:
        params = PaginationParams(
            page=int(request.query_params.get("page", 1)),
            limit=int(request.query_params.get("limit", 10)),
            sort_by=request.query_params.get("sort_by", "created_at"),
            order=request.query_params.get("order", "desc"),
        )
    except ValidationError as e:
        return response.json({"error": "Invalid query parameters", "details": e.errors()}, status_code=422)
    # Simulate paginated response
    users = [{"id": i, "username": f"user{i}"} for i in range(1, 6)]
    return response.json({"items": users, "total": len(users), "page": params.page, "limit": params.limit})
```

## 11. Advanced Templating (Inheritance, Context, Filters)

```python
from pathlib import Path
from nexios import NexiosApp
from nexios.templating import TemplateConfig, render

app = NexiosApp()
template_config = TemplateConfig(
    template_dir=Path("templates"), trim_blocks=True, lstrip_blocks=True
)
app.config.templating = template_config

@app.get("/")
async def home(request, response):
    return await render(
        "pages/home.html",
        {"title": "Home", "content": "Welcome!", "features": [
            {"name": "Fast", "description": "Built for speed"},
            {"name": "Secure", "description": "Security first"},
        ]},
    )
```

## 12. Advanced Routing (Typed Path Params, Wildcards)

```python
from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()

@app.get("/products/{product_id:int}")
async def get_product(req: Request, res: Response):
    product_id = req.path_params.product_id
    return res.json({"product_id": product_id, "type": "integer"})

@app.get("/categories/{category_name:str}")
async def get_category(req: Request, res: Response):
    category_name = req.path_params.category_name
    return res.json({"category_name": category_name, "type": "string"})

@app.get("/wildcard/{wildcard_path:path}")
async def get_wildcard(req: Request, res: Response):
    wildcard_path = req.path_params.wildcard_path
    return res.json({"wildcard_path": wildcard_path, "type": "path"})
```

## 13. Custom Response Types

```python
from nexios import NexiosApp
from nexios.http.response import (
    BaseResponse, FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
)

app = NexiosApp()


class XMLResponse(BaseResponse):
    media_type = "application/xml"

    def __init__(self, content, *args, **kwargs):
        import xml.etree.ElementTree as ET
        xml_content = ET.tostring(content, encoding="unicode")
        super().__init__(content=xml_content, *args, **kwargs)

@app.get("/json")
async def json_handler(req, res):
    return JSONResponse({"message": "Hello, World!"})

@app.get("/xml")
async def xml_handler(req, res):
    return XMLResponse({"message": "Hello, World!"})
```

---

For more, see the official Nexios documentation and the `examples/` folder in the repo. 