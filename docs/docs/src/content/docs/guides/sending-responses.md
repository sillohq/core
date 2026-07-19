---
title: Sending Responses
description: In sillo, sending responses is a core part of building web applications. The `Response` object provides a powerful and flexible way to construct and send HTTP responses to the client. This
  guide covers the various methods available for sending responses, from simple JSON to complex file downloads.
head:
- tag: meta
  attrs:
    property: og:title
    content: Sending Responses
- tag: meta
  attrs:
    property: og:description
    content: In sillo, sending responses is a core part of building web applications. The `Response` object provides a powerful and flexible way to construct and send HTTP responses to the client. This
      guide covers the various methods available for sending responses, from simple JSON to complex file downloads.
---
#  Sending Responses

Sending a response is a fundamental aspect of every HTTP request. sillo offers a well-rounded and robust framework designed to handle this process efficiently, ensuring clarity, flexibility, and performance in every interaction.

##  Basic Example

```py

@app.get("/users")
async def getUsers(request, response):
    return ["John Doe","Jane Smith"]
```
By default sillo turns `JSON-serializable` python data-types returned from route handlers as response which are sent to the client as json response 
 

##  Returning Various Data Types
You can return various data types from your route handlers:

```py title="List"
@app.get("/users")
async def getUsers(request, response):
    return ["John Doe","Jane Smith"]
```

```py title="String"
@app.get("/users")
async def getUsers(request, response):
    return "Hello World"
```

```py title="Dict"
@app.get("/users")
async def getUsers(request, response):
    return {"name": "John Doe", "age": 30}
```

```py title="Int"
@app.get("/users")
async def getUsers(request, response):
    return 200
```

```py title="Enum"
from sillo.status import HTTP_200_OK

@app.get("/users")
async def getUsers(request, response):
    return HTTP_200_OK
```


##  The `Response` Object
for complex responses you can use the `Response` object
the response object is passed as the second argument to your route handlers

```py
@app.get("/users")
async def getUsers(request, response):
    return response.json(["John Doe","Jane Smith"])
```

:::caution ⚠️ Important: Response Type Must Be Set First

When using the `Response` object, you **must** call one of the response type methods (`.json()`, `.html()`, `.text()`, `.file()`, `.stream()`, `.redirect()`, `.empty()`) **before** you can use methods like `.set_cookie()`, `.set_header()`, or `.status()`.

**This will cause an error:**
```py
@app.get("/users")
async def getUsers(request, response):
    # ❌ WRONG: Setting cookie before response type
    response.set_cookie("session", "abc123")
    return response.json(["John Doe","Jane Smith"])
```

**This is correct:**
```py
@app.get("/users")
async def getUsers(request, response):
    # ✅ CORRECT: Chain methods or set type first
    return response.json(["John Doe","Jane Smith"]).set_cookie("session", "abc123")
    
    # OR:
    response.json(["John Doe","Jane Smith"])
    response.set_cookie("session", "abc123")
    return response
```

:::

**Other Response Types**
```py title="JSON"
@app.get("/users")
async def getUsers(request, response):
    return response.json(["John Doe","Jane Smith"])
```

```py title="HTML"
@app.get("/users")
async def getUsers(request, response):
    return response.html("Hello World")
```

```py title="Text"
@app.get("/users")
async def getUsers(request, response):
    return response.text("Hello World")
```

```py title="File"
@app.get("/users")
async def getUsers(request, response):
    return response.file("path/to/file.txt")
```

```py title="Redirect"
@app.get("/users")
async def getUsers(request, response):
    return response.redirect("/users")
```

```py title="Streaming"
@app.get("/users")
async def getUsers(request, response):
    async def stream():
        for i in range(10):
            yield f"{i}\n"
    return response.stream(stream())
```


##  Sending Status Code
response object has a `status` method that allows you to set the status code of the response.

```py
@app.get("/users")
async def getUsers(request, response):
    return response.status(200).json(["John Doe","Jane Smith"])
```

::: tip  Recommended
For clarity and to leverage the full power of sillo's response handling, we recommend using the `response` object to build your responses, especially when you need to set custom headers, cookies, or status codes.
:::

### Chainable Responses

You can chain multiple methods together to configure the response before sending it. This makes your code more concise and expressive.

```python
from sillo import silloApp

app = silloApp()

@app.get("/")
async def home(req, res):
    res.status(200).set_cookie("session_id", "123").json({"message": "Hello, World!"})
```

::: tip Method Chaining vs Sequential Calls

You have two options when working with the response object:

**Option 1: Method Chaining (Recommended)**
```python
@app.get("/api/data")
async def get_data(req, res):
    return (res
            .status(200)
            .set_cookie("session", "abc123")
            .set_header("X-API-Version", "1.0")
            .json({"data": "success"}))
```

**Option 2: Sequential Calls**
```python
@app.get("/api/data")
async def get_data(req, res):
    res.json({"data": "success"})  # Set response type first
    res.set_cookie("session", "abc123")
    res.set_header("X-API-Version", "1.0")
    res.status(200)
    return res
```

Both approaches work, but chaining is more readable and ensures the response type is set before other operations.
In this example, we set the status code, add a cookie, and send a JSON response all in a single, chained statement.
:::

##  Aborting & Not Found

Sometimes you don't want to *build* an error response — you want to **stop
processing immediately** with an HTTP error. The response object provides two
short-circuit helpers that **raise** instead of returning a value:

- `response.abort(status_code, detail=...)` — raise a generic `HTTPException`.
- `response.not_found(detail=...)` — raise a `NotFoundException` (HTTP 404).

Because they raise, the framework's exception middleware catches them and
renders a consistent error envelope (JSON by default; HTML for 404 when
configured). You never call `return` after them.

### `response.abort()`

```python
from sillo import silloApp

app = silloApp()

@app.get("/admin")
async def admin(request, response):
    if not request.user.is_admin:
        response.abort(403, detail="Admins only")
    return response.json({"ok": True})
```

Calling `response.abort(403, detail="Admins only")` raises an
`HTTPException(status_code=403, detail="Admins only")`. The client receives a
`403` with a JSON body of `"Admins only"` (the detail is serialized directly).

You can also attach headers to the raised exception:

```python
@app.post("/login")
async def login(request, response):
    if not await authenticate(request):
        response.abort(401, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"})
    return response.json({"ok": True})
```

### `response.not_found()`

`not_found()` is a 404 shorthand. It raises `NotFoundException`, which the
framework routes through the registered 404 handler (supporting JSON, HTML, or
plain text based on configuration).

```python
@app.get("/items/{item_id:int}")
async def get_item(request, response, item_id: int):
    item = await db.get(item_id)
    if item is None:
        response.not_found(detail=f"Item {item_id} not found")
    return response.json(item)
```

A request to `/items/99` when no such item exists returns `404` with a JSON
body such as `{"status": 404, "error": "Not Found", "message": "Item 99 not found"}`.

### When to use `abort` vs building a response

Use `abort` / `not_found` when you want the **framework's error handling** to
apply (consistent envelopes, the configured 404 page, and centralized
logging). Use `response.status(404).json(...)` when you need a fully custom
body that bypasses the exception handlers.

::: warning These methods raise
Unlike `response.json()` or `response.empty()`, `abort()` and `not_found()` do
**not** return `self` and cannot be chained. They terminate the handler. Any
code after them will not run.
:::

##  Sending Different Types of Responses using the object directly 

sillo provides several methods for sending different types of responses.

### JSON Responses

To send a JSON response, use the `.json()` method. It automatically sets the `Content-Type` header to `application/json`.

```python
@app.get("/users")
async def get_users(req, res):
    users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    res.json(users)
```

### HTML Responses

To send an HTML response, use the `.html()` method. This will set the `Content-Type` header to `text/html`.

```python
@app.get("/welcome")
async def welcome(req, res):
    html_content = "<h1>Welcome to our website!</h1>"
    res.html(html_content)
```

### Plain Text Responses

For plain text responses, use the `.text()` method. The `Content-Type` will be set to `text/plain`.

```python
@app.get("/status")
async def status(req, res):
    res.text("Service is running.")
```

### Redirects

To redirect the client to a different URL, use the `.redirect()` method.

```python
@app.get("/old-path")
async def old_path(req, res):
    res.redirect("/new-path", status_code=301) # Permanent redirect
```

You can also redirect by route name instead of URL:

```python
@app.get("/user/{user_id}", name="user_profile")
async def get_user(req, res):
    res.json({"user_id": req.path_params.get("user_id")})

@app.get("/users")
async def list_users(req, res):
    # Redirect by route name - generates absolute URL
    res.redirect(name="user_profile", user_id=42)
```

##  Customizing the Response

You can customize the response by setting the status code, headers, and cookies.

### Setting the Status Code

Use the `.status()` method to set the HTTP status code.

```python
@app.post("/create-user")
async def create_user(req, res):
    # some logic to create a user
    res.status(201).json({"message": "User created successfully"})
```

### Setting Headers

Use the `.set_header()` method to add or modify HTTP headers.

```python
@app.get("/data")
async def get_data(req, res):
    res.set_header("Cache-Control", "no-cache").json({"data": "some data"})
```

### Setting Cookies

Use the `.set_cookie()` method to set a cookie on the client's browser.

```python
@app.post("/login")
async def login(req, res):
    res.set_cookie(
        key="user_token",
        value="secret-token",
        httponly=True,
        max_age=3600 # 1 hour
    ).json({"message": "Logged in"})
```

##  File Responses

sillo allows you to send files as responses using the `.file()` method. This is useful for serving images, documents, or other static assets.

```python
@app.get("/download-report")
async def download_report(req, res):
    file_path = "path/to/your/report.pdf"
    res.file(file_path, content_disposition_type="attachment")
```

By setting `content_disposition_type="attachment"`, you prompt the browser to download the file instead of displaying it.

##  Returning Data Directly

For simple cases, you can return a `dict`, `list`, or `str` directly from your handler. sillo will automatically convert it into a JSON response.

```python
@app.get("/simple")
async def simple_response(req, res):
    return {"message": "This is a simple response."}
```

::: tip When to Use Direct Returns vs Response Object

**Use direct returns when:**
- You only need to return simple data
- You don't need custom headers, cookies, or status codes
- You want the most concise code possible

**Use the Response object when:**
- You need to set custom headers or cookies
- You need specific HTTP status codes
- You need to serve files, HTML, or streaming content
- You need fine-grained control over the response

```python
# Simple case - direct return
@app.get("/users")
async def get_users(req, res):
    return [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

# Complex case - response object
@app.get("/users-with-metadata")
async def get_users_with_metadata(req, res):
    users = [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]
    return (res
            .status(200)
            .set_header("X-Total-Count", str(len(users)))
            .set_cookie("page", "1")
            .json({"data": users, "total": len(users)}))
```

:::

::: tip  Recommended
For clarity and to leverage the full power of sillo's response handling, we recommend using the `res` object to build your responses, especially when you need to set custom headers, cookies, or status codes.
:::

##  Advanced Usage: Response Classes

For more advanced use cases, sillo allows you to work directly with `Response` classes. This gives you the ultimate flexibility to control the response sent to the client. You can either use the built-in response classes or create your own.

### Using Built-in Response Classes

Instead of using the `res` object's methods, you can return an instance of a response class directly from your handler. sillo provides several built-in response classes in the `sillo.http.response` module.

*   `JSONResponse`
*   `HTMLResponse`
*   `PlainTextResponse`
*   `RedirectResponse`
*   `FileResponse`
*   `StreamingResponse`

**Example:**

```python
from sillo import silloApp
from sillo.http.response import JSONResponse, HTMLResponse

app = silloApp()

@app.get("/users-json")
async def get_users_json(req, res):
    users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    return JSONResponse(users, status_code=200)

@app.get("/welcome-html")
async def welcome_html(req, res):
    html_content = "<h1>Welcome from a Response class!</h1>"
    return HTMLResponse(html_content)
```

### Creating Custom Response Classes

You can create your own custom response classes by inheriting from `sillo.http.response.BaseResponse`. This is useful when you need to send responses in a format that is not supported out of the box, such as XML.

**Example: Creating an `XMLResponse` class**

```python
from sillo import silloApp
from sillo.http.response import BaseResponse
from dicttoxml import dicttoxml

class XMLResponse(BaseResponse):
    def __init__(self, content, *args, **kwargs):
        xml_content = dicttoxml(content)
        # BaseResponse stores the already-encoded body and a content_type
        super().__init__(body=xml_content, content_type="application/xml", *args, **kwargs)

app = silloApp()

@app.get("/data.xml")
async def get_xml_data(req, res):
    data = {"user": {"name": "John Doe", "id": "123"}}
    return XMLResponse(data)

```

In this example:

1.  We create a new `XMLResponse` class that inherits from `sillo.http.response.BaseResponse`.
2.  In the `__init__` method we convert the incoming `dict` to XML bytes with `dicttoxml`, then hand the encoded body and `content_type` to the parent class.
3.  Finally, we return an instance of our `XMLResponse` from the route handler.

By creating custom response classes, you can encapsulate response logic and reuse it across your application, leading to cleaner and more maintainable code.
