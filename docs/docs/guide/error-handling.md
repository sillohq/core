---
title: Error Handling in Nexios
description: Nexios provides a robust and flexible error handling system that allows you to manage exceptions gracefully and return appropriate responses to clients. This documentation covers all aspects of error handling in Nexios applications.
head:
  - - meta
    - property: og:title
      content: Error Handling in Nexios
  - - meta
    - property: og:description
      content: Nexios provides a robust and flexible error handling system that allows you to manage exceptions gracefully and return appropriate responses to clients. This documentation covers all aspects of error handling in Nexios applications.
---
# ⚠️ Error Handling

Nexios provides a robust and flexible error handling system that allows you to manage exceptions gracefully and return appropriate responses to clients. This documentation covers all aspects of error handling in Nexios applications.

## 🔍 The Basic Idea
```py
from nexios.exceptions import HTTPException

@app.get("/users/{user_id}")    
async def get_user(request, response):
    user = await find_user(request.path_params['user_id'])
    if not user:
        raise HTTPException(detail="User not found", status = 404)
    return response.json(user)

```


If you raise a non-HTTPException (e.g., raise ValueError("fail")), Nexios will return a 500 Internal Server Error unless you register a handler for that exception type.




## 🚨 HTTP Exceptions

Nexios includes built-in HTTP exceptions for common error scenarios:

```python{6}
from nexios.exceptions import HTTPException
@app.get("/users/{user_id}")
async def get_user(request, response):
    user = await find_user(request.path_params['user_id'])
    if not user:
        raise HTTPException(detail="User not found", status = 404)
    return response.json(user)

# If you raise a non-HTTPException (e.g., raise ValueError("fail")), Nexios will return a 500 Internal Server Error unless you register a handler for that exception type.
```

## 📝 Raising HTTP Exceptions
All HTTP exceptions accept these parameters:

- status_code: HTTP status code (required for base HTTPException)

- detail: Error message or details

- headers: Custom headers to include in the response

```python
raise HTTPException(
    status_code=400,
    detail="Invalid request parameters",
    headers={"X-Error-Code": "INVALID_PARAMS"}
)
```

## 🎨 Custom Exception Classes

Nexios provides a way to create custom exception classes that extend the built-in HTTPException class. This allows you to define specific error handling behavior for specific types of errors.

```python
from nexios.exceptions import HTTPException

class PaymentRequiredException(HTTPException):
    def __init__(self, detail: str = None):
        super().__init__(
            status_code=402,
            detail=detail or "Payment required",
            headers={"X-Payment-Required": "true"}
        )

@app.get("/premium-content")
async def get_premium_content(request, response):
    if not request.user.has_premium:
        raise PaymentRequiredException("Upgrade to premium to access this content")
    return response.json({"message": "Premium content available"})

# If your custom exception handler raises an error, Nexios will return a 500 error. Always handle exceptions in your handlers gracefully.
```

## 🛠️ Exception Handlers

Nexios provides a way to register custom exception handlers for specific exception types or HTTP status codes. This allows you to define custom error handling behavior for specific errors.

```python
from nexios.exceptions import HTTPException

async def handle_payment_required_exception(request, response, exception):
    return response.json({"error": "Payment required"}, status=402)

app.add_exception_handler(PaymentRequiredException, handle_payment_required_exception)

@app.get("/premium-content")
async def get_premium_content(request, response):
    if not request.user.has_premium:
        raise PaymentRequiredException("Upgrade to premium to access this content")
    return response.json({"message": "Premium content available"})      
``` 

## 📊 Status Code Handlers
Handle exceptions by status code:

```python
from nexios.exceptions import HTTPException

async def handle_payment_required_exception(request, response, exception):
    return response.json({"error": "Payment required"}, status=402)

app.add_exception_handler(402, handle_payment_required_exception)

@app.get("/premium-content")
async def get_premium_content(request, response):
    if not request.user.has_premium:
        raise PaymentRequiredException("Upgrade to premium to access this content")
    return response.json({"message": "Premium content available"})      
```


In the provided example, we demonstrate how to create a custom exception handler for handling specific exceptions in a Nexios application. We define a custom exception handler `handle_payment_required_exception`, which returns a JSON response with an error message and a status code when a `PaymentRequiredException` is raised. This handler is registered with the application using `app.add_exception_handler()`. This approach allows for granular control over error responses, improving the user experience by providing clear feedback for specific scenarios, such as when a user tries to access premium content without a subscription.


## 🖥️ Server Error Handler
Nexios provides a way to register a custom server error handler using the `server_error_handler` parameter from `NexiosApp`. This allows you to define custom error handling behavior for server errors.

```python
from nexios import NexiosApp
from nexios.exceptions import HTTPException

async def server_error_handler(request, response, exception):
    return response.json({"error": "Internal Server Error"}, status=500)

app = NexiosApp(server_error_handler=server_error_handler)
```

## 🔍 Debug Mode
Enable debug mode for detailed error responses:

```python

from nexios import MakeConfig

config = MakeConfig({"debug": True})
app = NexiosApp(config=config)
```

::: tip 🥹Tip

You can modify the app config simply as
app.config.debug = True
:::

## 🎯 Customizing 404 Not Found Responses

Nexios allows you to control how 404 Not Found errors are handled and presented to users. This is useful for providing a more user-friendly experience, matching your API or website style, or giving developers more debugging information during development.

### What is a 404 Not Found Error?
A **404 Not Found** error is a standard HTTP response code. It means the client (browser, API consumer, etc.) tried to access a URL or resource that doesn’t exist on your server. This could be a mistyped URL, a deleted resource, or a route that was never defined.

### Why Customize 404 Responses?
- **User Experience:** Show a branded or helpful error page/message.
- **API Consistency:** Ensure all errors follow your API's response format.
- **Debugging:** Show more details (like tracebacks) in development, but hide them in production.
- **Security:** In production, you may want to hide technical details to avoid leaking information about your app’s structure.

### How Nexios Handles 404s by Default
- If a route isn’t found, Nexios raises a `NotFoundException`.
- The default handler returns a simple JSON or HTML message, depending on the request and debug mode.

### How to Customize 404 Handling
You can add a `not_found` section to your application config. This controls the format and content of 404 responses. This is **not** a route or a handler you write yourself, but a set of options that tell Nexios how to respond when a 404 happens.

#### Available Options
| Option           | Type   | What it Does                                                                 | When to Use It                        |
|------------------|--------|------------------------------------------------------------------------------|---------------------------------------|
| `return_json`    | bool   | If `True`, respond with JSON. If `False`, use HTML or plain text.            | APIs: `True`, Websites: `False`       |
| `custom_message` | str    | The message shown for 404 errors (when not in debug mode).                   | Branding, user-friendliness           |
| `show_traceback` | bool   | If `True` and debug is on, include a Python traceback in the response.       | Development only                      |
| `use_html`       | bool   | If `True`, use an HTML error page (if not returning JSON).                   | Websites, or pretty error pages       |

#### Example: Custom 404 Config
```python
from nexios import NexiosApp
from nexios.config import MakeConfig

config = MakeConfig({
    # ... other config options ...
    "not_found": {
        "return_json": True,  # Set to False for HTML/plain text
        "custom_message": "Sorry, this page does not exist.",
        "show_traceback": False,  # Only relevant if debug is True
        "use_html": False,  # Set to True for HTML error page
    }
})

app = NexiosApp(config=config)
```

#### How it Works
- If `return_json` is `True`, the response will be JSON:
  ```json
  {"status": 404, "error": "Not Found", "message": "Sorry, this page does not exist."}
  ```
- If `use_html` is `True` and `return_json` is `False`, an HTML error page is shown.
- If both are `False`, a plain text message is returned.
- If `show_traceback` is `True` and debug mode is on, the response (JSON or HTML) will include a Python traceback, which helps you debug why the route wasn’t found.

#### Real-World Scenarios
**A. API-First Project**
You want all errors, including 404s, to be JSON so your frontend or mobile app can handle them consistently.
```python
config = MakeConfig({
    "not_found": {
        "return_json": True,
        "custom_message": "Resource not found.",
        "show_traceback": False,
        "use_html": False,
    }
})
```

**B. Marketing Website**
You want a pretty, branded HTML error page for users who mistype a URL.
```python
config = MakeConfig({
    "not_found": {
        "return_json": False,
        "custom_message": "Oops! We couldn't find that page.",
        "show_traceback": False,
        "use_html": True,
    }
})
```

**C. Developer Debugging**
You want to see tracebacks for 404s while developing, but not in production.
```python
config = MakeConfig({
    "debug": True,
    "not_found": {
        "return_json": True,
        "custom_message": "Not here!",
        "show_traceback": True,
        "use_html": False,
    }
})
```

#### Summary Table
| Use Case         | return_json | use_html | show_traceback | custom_message                |
|------------------|-------------|----------|---------------|-------------------------------|
| API              | True        | False    | False         | "Resource not found."         |
| Website          | False       | True     | False         | "Sorry, this page does not exist." |
| Debugging        | True/False  | Any      | True          | Any                           |



> **Tip:** You can change these settings at runtime by updating your config and calling `set_config()`.