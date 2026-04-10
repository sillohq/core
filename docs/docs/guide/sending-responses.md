---
title: Sending Responses
description: In Nexios, sending responses is a core part of building web applications. The `Response` object provides a powerful and flexible way to construct and send HTTP responses to the client. This guide covers the various methods available for sending responses, from simple JSON to complex file downloads.
head:
  - - meta
    - property: og:title
      content: Sending Responses
  - - meta
    - property: og:description
      content: In Nexios, sending responses is a core part of building web applications. The `Response` object provides a powerful and flexible way to construct and send HTTP responses to the client. This guide covers the various methods available for sending responses, from simple JSON to complex file downloads.
---
#  Sending Responses

Sending a response is a fundamental aspect of every HTTP request. Nexios offers a well-rounded and robust framework designed to handle this process efficiently, ensuring clarity, flexibility, and performance in every interaction.

##  Basic Example

```py

@app.get("/users")
async def getUsers(request, response):
    return ["John Doe","Jane Smith"]
```
By default nexios turns `JSON-serializable` python data-types returned from route handlers as response which are sent to the client as json response 
 

##  Returning Various Data Types
You can return various data types from your route handlers:

::: code-group


```py [List]
@app.get("/users")
async def getUsers(request, response):
    return ["John Doe","Jane Smith"]
```

```py [String]
@app.get("/users")
async def getUsers(request, response):
    return "Hello World"
```

```py [Dict]
@app.get("/users")
async def getUsers(request, response):
    return {"name": "John Doe", "age": 30}
```

```py [Int]
@app.get("/users")
async def getUsers(request, response):
    return 200
```

```py [Enum]
@app.get("/users")
async def getUsers(request, response):
    return StatusCodes.OK
```
:::

##  The `Response` Object
for complex responses you can use the `Response` object
the response object is passed as the second argument to your route handlers

```py
@app.get("/users")
async def getUsers(request, response):
    return response.json(["John Doe","Jane Smith"])
```

::: warning ⚠️ Important: Response Type Must Be Set First

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
::: code-group

```py [JSON]
@app.get("/users")
async def getUsers(request, response):
    return response.json(["John Doe","Jane Smith"])
```

```py [HTML]
@app.get("/users")
async def getUsers(request, response):
    return response.html("Hello World")
```

```py [Text]
@app.get("/users")
async def getUsers(request, response):
    return response.text("Hello World")
```

```py [File]
@app.get("/users")
async def getUsers(request, response):
    return response.file("path/to/file.txt")
```

```py [Redirect]
@app.get("/users")
async def getUsers(request, response):
    return response.redirect("/users")
```

```py [Streaming]
@app.get("/users")
async def getUsers(request, response):
    async def stream():
        for i in range(10):
            yield f"{i}\n"
    return response.stream(stream())
```
:::

##  Sending Status Code
response object has a `status` method that allows you to set the status code of the response.

```py
@app.get("/users")
async def getUsers(request, response):
    return response.status(200).json(["John Doe","Jane Smith"])
```

::: tip  Recommended
For clarity and to leverage the full power of Nexios's response handling, we recommend using the `response` object to build your responses, especially when you need to set custom headers, cookies, or status codes.
:::

### Chainable Responses

You can chain multiple methods together to configure the response before sending it. This makes your code more concise and expressive.

```python
from nexios import NexiosApp

app = NexiosApp()

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
##  Sending Different Types of Responses using the object directly 

Nexios provides several methods for sending different types of responses.

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

Nexios allows you to send files as responses using the `.file()` method. This is useful for serving images, documents, or other static assets.

```python
@app.get("/download-report")
async def download_report(req, res):
    file_path = "path/to/your/report.pdf"
    res.file(file_path, content_disposition_type="attachment")
```

By setting `content_disposition_type="attachment"`, you prompt the browser to download the file instead of displaying it.

##  Returning Data Directly

For simple cases, you can return a `dict`, `list`, or `str` directly from your handler. Nexios will automatically convert it into a JSON response.

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
For clarity and to leverage the full power of Nexios's response handling, we recommend using the `res` object to build your responses, especially when you need to set custom headers, cookies, or status codes.
:::

##  Advanced Usage: Response Classes

For more advanced use cases, Nexios allows you to work directly with `Response` classes. This gives you the ultimate flexibility to control the response sent to the client. You can either use the built-in response classes or create your own.

### Using Built-in Response Classes

Instead of using the `res` object's methods, you can return an instance of a response class directly from your handler. Nexios provides several built-in response classes in the `nexios.http.response` module.

*   `JSONResponse`
*   `HTMLResponse`
*   `TextResponse`
*   `RedirectResponse`
*   `FileResponse`
*   `StreamingResponse`

**Example:**

```python
from nexios import NexiosApp
from nexios.http.response import JSONResponse, HTMLResponse

app = NexiosApp()

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

You can create your own custom response classes by inheriting from `nexios.http.response.Response`. This is useful when you need to send responses in a format that is not supported out of the box, such as XML.

**Example: Creating an `XMLResponse` class**

```python
from nexios import NexiosApp
from nexios.http.response import Response
from dicttoxml import dicttoxml

class XMLResponse(Response):
    media_type = "application/xml"

    def __init__(self, content, *args, **kwargs):
        xml_content = dicttoxml(content)
        super().__init__(content=xml_content, *args, **kwargs)

app = NexiosApp()

@app.get("/data.xml")
async def get_xml_data(req, res):
    data = {"user": {"name": "John Doe", "id": "123"}}
    return XMLResponse(data)

```

In this example:

1.  We create a new `XMLResponse` class that inherits from `nexios.http.response.Response`.
2.  We set the `media_type` to `application/xml`.
3.  In the `__init__` method, we convert the incoming `dict` to XML using the `dicttoxml` library before passing it to the parent class.
4.  Finally, we return an instance of our `XMLResponse` from the route handler.

By creating custom response classes, you can encapsulate response logic and reuse it across your application, leading to cleaner and more maintainable code.
