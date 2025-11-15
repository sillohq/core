# 🚀 Why Migrating to Nexios is Worth It

Migrating to Nexios is a worthwhile investment for several reasons:

Nexios is built on top of [ASGI](https://asgi.readthedocs.io/) 🌐, a newer async server interface for Python. While [WSGI](https://wsgi.readthedocs.io/) is older and less efficient, ASGI offers superior performance and scalability. Nexios leverages ASGI to provide a high-performance web framework for modern Python applications.

Additionally, Nexios promotes clean code practices, making it easier to write maintainable and testable code. The framework is designed to be easy to use, with a consistent and intuitive API. Lastly, Nexios is less opinionated about project structure, allowing you to adapt it to your needs.

---

## 🛣️ Routing

Routing is how frameworks map an incoming HTTP request to a handler function. Each framework has its own way of registering routes.

::: code-group

```python [Nexios (with decorator)]
from nexios import NexiosApp
app = NexiosApp()

@app.get("/hello")
async def hello(request, response):
    return response.json({"message": "Hello from Nexios"})
```

```python [Nexios (without decorator)]
from nexios import NexiosApp
from nexios.routing import Route

app = NexiosApp()

async def hello(request, response):
    return response.json({"message": "Hello from Nexios"})

route = Route("/hello", hello, methods=["GET"])
app.add_route(route)
```

```python [Flask]
from flask import Flask

app = Flask(__name__)

@app.route("/hello")
def hello():
    return {"message": "Hello from Flask"}
```

```python [FastAPI]
from fastapi import FastAPI

app = FastAPI()

@app.get("/hello")
async def hello():
    return {"message": "Hello from FastAPI"}
```

```python [Starlette]
from starlette.applications import Starlette
from starlette.responses import JSONResponse

app = Starlette()

@app.route("/hello")
async def hello(request):
    return JSONResponse({"message": "Hello from Starlette"})
```

:::

---

## ⚙️ Handler Signature

A handler (or view) is just a Python function that receives the request and returns a response. Nexios passes both `request` and `response` explicitly, while Flask, FastAPI, and Starlette either auto-inject or expose only `request`.

::: code-group

```python [Nexios]
from nexios import NexiosApp

app = NexiosApp()

@app.get("/hello")
async def hello(request, response):
    return {"message": "Hello from Nexios"}
```

```python [Flask]
from flask import Flask

app = Flask(__name__)

@app.route("/hello")
def hello():
    return {"message": "Hello from Flask"}
```

```python [FastAPI]
from fastapi import FastAPI

app = FastAPI()

@app.get("/hello")
async def hello():
    return {"message": "Hello from FastAPI"}
```

```python [Starlette (with decorator)]
from starlette.applications import Starlette
from starlette.responses import JSONResponse

app = Starlette()

@app.route("/hello")
async def hello(request):
    return JSONResponse({"message": "Hello from Starlette"})
```

```python [Starlette (without decorator)]
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

async def hello(request):
    return JSONResponse({"message": "Hello from Starlette"})

app = Starlette(routes=[Route("/hello", hello)])
```

:::

---

## 📋 Request Object

Every web framework exposes a `Request` object that allows you to inspect the incoming HTTP request. The exact API differs across frameworks.

| Feature              | Nexios Example               | Flask Example                  | FastAPI Example                     | Starlette Example                 |
| -------------------- | ---------------------------- | ------------------------------ | ----------------------------------- | --------------------------------- |
| Query Params         | `request.query_params["id"]` | `request.args.get("id")`       | `id: int` as function param         | `request.query_params["id"]`      |
| JSON Body            | `await request.json`         | `request.get_json()`           | Pydantic model / `await req.json()` | `await request.json()`            |
| Form Data            | `await request.form`         | `request.form["field"]`        | `Form(...)` dependency              | `await request.form()`            |
| Path Params          | `request.path_params["id"]`  | `<id>` in route & function arg | Defined in route + function arg     | `request.path_params["id"]`       |
| Headers              | `request.headers["auth"]`    | `request.headers.get("auth")`  | `headers: dict = request.headers`   | `request.headers["auth"]`         |
| Cookies              | `request.cookies["token"]`   | `request.cookies.get("token")` | `cookie: str = Cookie(...)`         | `request.cookies["token"]`        |
| Client IP            | `request.client.host`        | `request.remote_addr`          | `request.client.host`               | `request.client.host`             |
| Method               | `request.method`             | `request.method`               | `request.method`                    | `request.method`                  |
| URL                  | `request.url`                | `request.url`                  | `request.url`                       | `request.url`                     |
| Session (if enabled) | `request.session["user"]`    | `session["user"]`              | Middleware extension                | Middleware/session extension      |
| Files (multipart)    | `await request.files`        | `request.files["file"]`        | `UploadFile` in params              | `await request.form()` → file obj |
| Raw Body             | `await request.body`         | `request.data`                 | `await request.body()`              | `await request.body()`            |

---

## 📤 Sending Response

Returning a response can be as simple as returning a dictionary (which Nexios, Flask, and FastAPI auto-serialize to JSON) or manually constructing a `Response` object for more control.

::: code-group

```python [Nexios]
from nexios import NexiosApp
from nexios.http.responses import JSONResponse

app = NexiosApp()

@app.get("/data")
async def data(request, response):
    return {"message": "Nexios JSON"}

    # or  manually
    return JSONResponse({"message": "Nexios JSON"})

    # or using response object
    return response.json({"message": "Nexios JSON"})
```

```python [Flask]
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/data")
def data():
    return jsonify({"message": "Flask JSON"})
```

```python [FastAPI]
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/data")
async def data():
    return JSONResponse({"message": "FastAPI JSON"})
```

```python [Starlette]
from starlette.applications import Starlette
from starlette.responses import JSONResponse

app = Starlette()

@app.route("/data")
async def data(request):
    return JSONResponse({"message": "Starlette JSON"})
```

:::

---

## 📁 Static Files

Static files (images, CSS, JavaScript) can be served natively. ASGI-based frameworks use `StaticFiles`, while Flask has built-in static folder support.

::: code-group

```python [Nexios]
from nexios import NexiosApp
from nexios.static import StaticFiles

app = NexiosApp()
app.register(StaticFiles(directory="public"), prefix="/static")
```

```python [Flask]
from flask import Flask

app = Flask(__name__, static_folder="public", static_url_path="/static")
```

```python [FastAPI]
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/static", StaticFiles(directory="public"), name="static")
```

```python [Starlette]
from starlette.applications import Starlette
from starlette.staticfiles import StaticFiles

app = Starlette()
app.mount("/static", StaticFiles(directory="public"), name="static")
```

:::

---

## 🛡️ Error Handling

Error handling lets you intercept exceptions and return custom responses. Nexios, FastAPI, and Starlette have async exception handlers, while Flask uses decorators.

::: code-group

```python [Nexios]
from nexios import NexiosApp
from nexios.exceptions import HTTPException

app = NexiosApp()

@app.add_exception_handler(404)
async def not_found(request, response, exc):
    return response.json({"error": "Not Found"}, status=404)

#or add exceptions classed directly
@app.add_exception_handler(HTTPException)
async def server_error(request, response, exc):
    return response.json({"error": "Internal Server Error"}, status=500)

# without using decorator

app.add_exception_handler(HTTPException, server_error)
```

```python [Flask]
from flask import Flask, jsonify

app = Flask(__name__)

@app.errorhandler(404)
def not_found(e):
    return jsonify(error="Not Found"), 404
```

```python [FastAPI]
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(404)
async def not_found(request: Request, exc):
    return JSONResponse({"error": "Not Found"}, status_code=404)
```

```python [Starlette]
from starlette.applications import Starlette
from starlette.responses import JSONResponse

app = Starlette()

@app.exception_handler(404)
async def not_found(request, exc):
    return JSONResponse({"error": "Not Found"}, status_code=404)
```

:::

---

## 💉 Dependency Injection (DI)

Dependency Injection allows you to cleanly separate concerns (like database access, services). Nexios and FastAPI have first-class DI support, while Flask/Starlette don’t provide it natively.

::: code-group

```python [Nexios]
from nexios import NexiosApp, Depends

app = NexiosApp()

def get_user_service():
    return {"name": "Dunamis"}

@app.get("/profile")
async def profile(request, response, user = Depends(get_user_service)):
    return user
```

```python [FastAPI]
from fastapi import FastAPI, Depends

app = FastAPI()

def get_user_service():
    return {"name": "Dunamis"}

@app.get("/profile")
async def profile(user = Depends(get_user_service)):
    return user
```

:::

---

## 📡 WebSockets

WebSockets provide two-way real-time communication. Flask doesn’t support WebSockets natively, but Nexios, FastAPI, and Starlette do.

::: code-group

```python [Nexios]
from nexios import NexiosApp
from nexios.websocket import WebSocket
app = NexiosApp()

@app.ws_route("/ws")
async def ws_handler(ws:WebSocket):
    await ws.accept()
    await ws.send_json({"msg": "Hello WebSocket"})
```

```python [FastAPI]
from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    await ws.send_json({"msg": "Hello WebSocket"})
```

```python [Starlette]
from starlette.applications import Starlette
from starlette.endpoints import WebSocketEndpoint

app = Starlette()

@app.websocket_route("/ws")
class Echo(WebSocketEndpoint):
    async def on_connect(self, ws):
        await ws.accept()
        await ws.send_json({"msg": "Hello WebSocket"})
```

:::
