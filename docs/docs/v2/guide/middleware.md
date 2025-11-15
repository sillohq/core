---
title: Middleware
icon: jsfiddle
description: Middleware in Nexios is a powerful feature that allows you to intercept, process, and modify requests and responses as they flow through your application. It acts as a pipeline, enabling you to implement cross-cutting concerns such as logging, authentication, validation, and response modification in a modular and reusable way. This documentation provides a comprehensive guide to understanding and using middleware in Nexios.
head:
  - - meta
    - property: og:title
      content: Middleware
  - - meta
    - property: og:description
      content: Middleware in Nexios is a powerful feature that allows you to intercept, process, and modify requests and responses as they flow through your application. It acts as a pipeline, enabling you to implement cross-cutting concerns such as logging, authentication, validation, and response modification in a modular and reusable way. This documentation provides a comprehensive guide to understanding and using middleware in Nexios.
---

# Middleware

Middleware in Nexios is a powerful feature that allows you to intercept, process, and modify requests and responses as they flow through your application. It acts as a pipeline, enabling you to implement cross-cutting concerns such as logging, authentication, validation, and response modification in a modular and reusable way. This documentation provides a comprehensive guide to understanding and using middleware in Nexios.

Middleware in Nexios provides:

- **Request/Response Pipeline**: Process requests before and after handlers
- **Cross-cutting Concerns**: Implement logging, auth, CORS, etc. once
- **Modular Design**: Each middleware has a single responsibility
- **Reusability**: Middleware can be shared across different routes
- **Order Control**: Middleware executes in the order they're added
- **Error Handling**: Middleware can catch and handle exceptions




---

## **How Middleware Works**

Middleware functions are executed in a sequence, forming a pipeline that processes incoming requests and outgoing responses. Each middleware function has access to the request (`req`), response (`res`), and a `next` function to pass control to the next middleware or the final route handler.

### **Key Responsibilities of Middleware**

- **Modify the Request** – Add headers, parse data, or inject additional context.
- **Block or Allow Access** – Enforce authentication, rate limiting, or other access controls.
- **Modify the Response** – Format responses, add headers, or compress data.
- **Pass Control** – Call `next()` to continue processing the request or terminate early.

::: tip Middleware Flow
The middleware pipeline follows this pattern:

1. **Pre-processing**: Execute code before the handler
2. **Call next()**: Pass control to the next middleware or handler
3. **Post-processing**: Execute code after the handler returns
4. **Return response**: Send the final response back to the client
   :::

## **Basic Middleware Example**

Below is a simple example demonstrating how to define and use middleware in a Nexios application:

```python
from nexios import NexiosApp
from datetime import datetime
app = NexiosApp()

# Middleware 1: Logging
async def my_logger(req, res, next):
    print(f"Received request: {req.method} {req.path}")
    await next()  # Pass control to the next middleware or handler
    # If you forget to call await next(), the request will hang or time out and the client will not receive a response.

# Middleware 2: Request Timing
async def request_time(req, res, next):
    req.request_time = datetime.now()  # Store request time in context
    await next()

# Middleware 3: Cookie Validation
async def validate_cookies(req, res, next):
    if "session_id" not in req.cookies:
        return res.json({"error": "Missing session_id cookie"}, status_code=400)
    await next()
    # If you return a response before calling next(), the pipeline is short-circuited and no further middleware or handlers will run. This is useful for early exits, such as authentication failures.

# Add middleware to the application
app.add_middleware(my_logger)
app.add_middleware(request_time)
app.add_middleware(validate_cookies)

# Route Handler
@app.get("/")
async def hello_world(req, res):
    return res.text("Hello, World!")

```

::: tip 💡Tip
All code before `await next()` is executed before the route handler.
:::

## **Order of Execution**

Middleware functions are executed in the order they are added. The flow of execution is as follows:

1. **Pre-Processing** – Middleware functions execute before the route handler.
2. **Route Handler** – The request is processed by the route handler.
3. **Post-Processing** – Middleware functions execute after the route handler.

```
   Incoming request
 └──> Middleware 1 (logs)
       └──> Middleware 2 (auth check)
             └──> Route handler (e.g., /profile)
                   └──> Response is built
             ←──── Middleware 2 resumes (e.g., modify response)
       ←──── Middleware 1 resumes
←──── Final response sent

```

::: tip 💡Tip
Middleware functions are executed in the order they are added. Ensure that middleware with dependencies (e.g., authentication before authorization) is added in the correct sequence.
:::

---

## What is `cnext`?

In Nexios, middleware functions rely on a continuation callback (commonly called next, cnext, or callnext) to pass control to the next stage of the request pipeline. This parameter is crucial for request flow but its name is completely flexible — you're free to call it whatever makes sense for your codebase.

## Before and after handler
For example, let's say we want to log the time it takes for a request to complete. We can write a middleware that will log the time before and after the handler is called:

```python
from nexios import NexiosApp

app = NexiosApp()

async def log_time(req, res, next):
    start_time = time.time() #  Get current time Before handler
    await next()
    end_time = time.time() # Get current time After handler
    print(f"Request {req.method} {req.url} took {end_time - start_time} seconds")

app.add_middleware(log_time)
```
You can also modify the request and response object before and after handler

```python
from nexios import NexiosApp

app = NexiosApp()

async def modify_request(req, res, next):
    req.state.name = "John"
    
    await next()
    res.set_header("X-Custom-Header", "Custom Value") # Set header after handler

app.add_middleware(modify_request)

@app.get("/")
async def index(req, res):
    return res.text(f"Hello, {req.state.name}")
```


::: warning ⚠️ Warning

Modifying the response object should be done after the request is processed. It's best to use the `process_response` method of middleware or `callnext`

:::

## **Class-Based Middleware**

Nexios supports class-based middleware for better organization and reusability. A class-based middleware must inherit from `BaseMiddleware` and implement the following methods:

- **`process_request(req, res, cnext)`** – Executed before the request reaches the handler.
- **`process_response(req, res)`** – Executed after the handler has processed the request.

### **Example: Class-Based Middleware**

```python
from nexios.middleware import BaseMiddleware

class ExampleMiddleware(BaseMiddleware):
    async def process_request(self, req, res, cnext):
        """Executed before the request handler."""
        print("Processing Request:", req.method, req.url)
        await cnext()  # Pass control to the next middleware or handler
        # If you use the wrong parameter order in your methods, Nexios will raise an error at startup.
        # If you forget to call await cnext(req, res), the request will not reach the handler and the client will not receive a response.

    async def process_response(self, req, res):
        """Executed after the request handler."""
        print("Processing Response:", res.status_code)
        return res  # Must return the modified response
        # If you forget to return the response in process_response, the client will not receive the intended response.
```

### **Method Breakdown**

1. **`process_request(req, res, cnext)`**
   - Used for pre-processing tasks like logging, authentication, or data injection.
   - Must call `await cnext(req, res)` to continue processing.
2. **`process_response(req, res)`**
   - Used for post-processing tasks like modifying the response or logging.
   - Must return the modified `res` object.


 If you forget to return the response in process_response, the client will not receive the intended response.

If you use the wrong parameter order in your methods, Nexios will raise an error at startup.

:::  tip Note
you can handle errors in middleware by wrapping logic in try/except and returning a custom error response.
:::

```python
from nexios.middleware import BaseMiddleware

class ErrorCatchingMiddleware(BaseMiddleware):
    async def process_request(self, req, res, cnext):
        try:
            await cnext(req, res)
        except Exception as exc:
            return res.json({"error": str(exc)}, status_code=500)
    # If you raise an error in middleware and do not handle it, Nexios will return a 500 error. Always use try/except for critical middleware logic.

    async def process_response(self, req, res):
        return res

```

---

## **Using make_response in Middleware**

The `make_response` method in Nexios allows you to create custom response objects within your middleware. This is particularly useful when you need to:

- Create custom response types not directly supported by the built-in response methods
- Implement response transformations or wrappers
- Handle specific response formatting requirements

### **Basic Usage**

```python
from nexios.http.response import JSONResponse, HTMLResponse

async def custom_response_middleware(req, res, next):
    # Create a custom JSON response
    res.make_response(JSONResponse({"message": "Hello, World!"}))
    
    

    # Note: If you don't return the response, the original response will be used
    # If you need to continue with the normal flow, call await next()
```
::: warning ⚠️ Warning
Avoid raising exceptions in middleware. Instead, handle errors gracefully and return a custom error response. Raising exceptions can lead to unexpected behavior, security issues, or a 500 error for the client.
:::


### **Example: Custom Error Response**

```python
from nexios.http.response import JSONResponse

async def error_handler_middleware(req, res, next):
    try:
        await next()
    except Exception as e:
        # Create a custom error response
        error_response = res.json(
            {
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "code": getattr(e, "code", "UNKNOWN_ERROR")
                }
            },
            status_code=getattr(e, "status_code", 500)
        )
        
        return error_response

    return res
```

## **Route-Specific Middleware**

Route-specific middleware applies only to a particular route. This is useful for applying middleware logic to specific endpoints without affecting the entire application.

### **Example: Route-Specific Middleware**

```python
async def auth_middleware(req, res, cnext):
    if not req.headers.get("Authorization"):
        return res.json({"error": "Unauthorized"}, status_code=401)
    await cnext(req, res)
    # If you forget to call await cnext() in route-specific middleware, the request will not reach the handler and the client will not receive a response.

@app.route("/profile", "GET", middleware=[auth_middleware])
async def get_profile(req, res):
    return res.json({"message": "Welcome to your profile!"})
```

**⚙️ Execution Order:**\
`auth_middleware → get_profile handler → response sent`

# If you forget to call await cnext() in route-specific middleware, the request will not reach the handler.

---

## **Router-Specific Middleware**

Router-specific middleware applies to all routes under a specific router. This is useful for grouping middleware logic for a set of related routes.

### **Example: Router-Specific Middleware**

```python
admin_router = Router()

async def admin_auth(req, res, cnext):
    if not req.headers.get("Admin-Token"):
        return res.json({"error": "Forbidden"}, status_code=403)
    await cnext(req, res)
    # Returning a response before calling cnext will stop further processing for this request.

admin_router.add_middleware(admin_auth)  # Applies to all routes inside admin_router

@admin_router.route("/dashboard", "GET")
async def dashboard(req, res):
    return res.json({"message": "Welcome to the admin dashboard!"})

app.mount_router("/admin", admin_router)  # Mount router at "/admin"
```

**Execution Order:**\
`admin_auth → dashboard handler → response sent`

---

## **Nexios Middleware vs. ASGI Middleware**

Nexios offers two ways to add middleware to your application: `app.add_middleware()` and `app.wrap_asgi()`. While both are used to hook into the request/response lifecycle, they serve different purposes and are designed for different types of middleware.

### **`add_middleware`: For Nexios-Specific Middleware**

The `app.add_middleware()` method is designed for middleware that is tightly integrated with the Nexios framework. This type of middleware operates on Nexios's `Request` and `Response` objects, giving you access to the rich features and abstractions that Nexios provides.

**When to use `add_middleware`:**

- You want to interact with Nexios-specific objects like `Request` and `Response`.
- Your middleware needs to access path parameters, parsed query parameters, or the request body in a convenient way.
- You want to take advantage of Nexios's dependency injection system within your middleware.

**Example:**

```python
from nexios import NexiosApp, Request, Response

app = NexiosApp()

async def nexios_style_middleware(req: Request, res: Response, next_call):
    # This middleware has access to the Nexios Request and Response objects
    print(f"Request path: {req.path}")
    print(f"Query params: {req.query_params}")
    await next_call()
    res.set_header("X-Nexios-Middleware", "true")

app.add_middleware(nexios_style_middleware)

@app.get("/")
async def home(req: Request, res: Response):
    res.send("Hello from Nexios!")
```

### **`wrap_asgi`: For Standard ASGI Middleware**

The `app.wrap_asgi()` method is used to add standard ASGI middleware to your application. ASGI middleware is a lower-level type of middleware that conforms to the ASGI specification. It operates directly on the raw ASGI `scope`, `receive`, and `send` callables.

This is particularly useful when you want to use third-party ASGI middleware that is not specific to Nexios.

**When to use `wrap_asgi`:**

- You need to integrate a third-party ASGI middleware (e.g., from a library like `asgi-correlation-id`).
- Your middleware needs to operate at a lower level, before the request is processed by Nexios's routing and request/response handling.
- The middleware is designed to be framework-agnostic.

**Example (using a hypothetical third-party ASGI middleware):**

Let's say you have a third-party library that provides a GZip middleware for ASGI applications.

```python
from nexios import NexiosApp
from some_asgi_library import GZipMiddleware  # A hypothetical third-party middleware

app = NexiosApp()

# Wrap the Nexios application with the third-party ASGI middleware
app.wrap_asgi(GZipMiddleware, minimum_size=1000)

@app.get("/")
async def home(req, res):
    # The response will be gzipped by the middleware if it's large enough
    res.send("This is a long string that will hopefully be compressed." * 100)
```

### **When to Use Which?**

| Feature                | `add_middleware`                                       | `wrap_asgi`                                             |
| ---------------------- | ------------------------------------------------------ | ------------------------------------------------------- |
| **Abstraction Level**  | High-level (Nexios `Request`/`Response`)               | Low-level (ASGI `scope`, `receive`, `send`)             |
| **Framework Specific** | Nexios-specific                                        | Framework-agnostic (standard ASGI)                      |
| **Use Case**           | Business logic, auth, interacting with Nexios features | Third-party middleware, low-level request manipulation  |
| **Example**            | Custom logging, modifying Nexios `Response`            | GZip compression, CORS handling from a standard library |

By understanding the difference between these two methods, you can choose the right tool for the job and build more powerful and flexible applications with Nexios.

## **Using `@use_for_route` Decorator**

The `@use_for_route` decorator binds a middleware function to specific routes or route patterns, ensuring that the middleware only executes when a matching route is accessed.

### **Example: `@use_for_route` Decorator**

```python
from nexios.middleware.utils import use_for_route

@use_for_route("/dashboard")
async def log_middleware(req, res, cnext):
    print(f"User accessed {req.path.url}")
    await cnext()  # Proceed to the next function (handler or middleware)
```

---

Always call `await next()` in middleware to ensure the request continues processing. Failing to do so will block the request pipeline.

::: warning ⚠️ Warning
Avoind modifying the request object in middleware. This can lead to unexpected behavior or security issues.

:::



## Raw ASGI Middleware

Nexios allows you to use raw ASGI middleware for scenarios where you need lower-level control over the ASGI protocol. This is especially useful when integrating with third-party ASGI middleware, performing operations that require direct access to the ASGI `scope`, or when you need to manipulate the request/response cycle before Nexios processes the request.

Raw ASGI middleware operates directly on the `scope`, `receive`, and `send` callables, and is completely framework-agnostic. Unlike Nexios middleware, it does not have access to Nexios-specific abstractions like `Request` or `Response` objects.

### Function-Based Raw Middleware

A function-based raw middleware wraps the ASGI app and must call the next app in the chain. If you forget to call `await app(scope, receive, send)`, the request will never reach the application and the client will hang.

```python
def raw_middleware(app):
    async def middleware(scope, receive, send):
        # You can inspect or modify the scope here
        # For example, add a custom key:
        scope["custom_key"] = "custom_value"
        # Always call the next app in the chain
        await app(scope, receive, send)
    return middleware

app.wrap_asgi(raw_middleware)
```

If you modify the `scope`, be careful not to overwrite required ASGI keys or introduce security issues. Always validate any changes you make.

### Class-Based Raw Middleware

A class-based raw middleware provides more flexibility and can maintain state between requests if needed. The class must implement the `__call__` method and accept the ASGI app as its first argument.

```python
class RawMiddleware:
    def __init__(self, app, *args, **kwargs):
        self.app = app
        # You can store args/kwargs for configuration

    async def __call__(self, scope, receive, send):
        # Perform actions before the request is processed
        # For example, log the incoming scope
        print(f"ASGI scope: {scope}")
        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            # Handle errors gracefully
            print(f"Error in raw middleware: {exc}")
            raise
        # You can also perform actions after the response is sent

app.wrap_asgi(RawMiddleware, some_option=True)
```

If you raise an error in raw middleware and do not handle it, the client will receive a 500 error. Always use try/except for critical logic.

### When to Use Raw Middleware

- Integrating third-party ASGI middleware (e.g., CORS, GZip, Sentry, etc.)
- Performing low-level request/response manipulation before Nexios processes the request
- Adding features that require direct access to the ASGI protocol
- Ensuring compatibility with other ASGI frameworks or tools

### Common Mistakes

- Not calling `await app(scope, receive, send)`: The request will hang and the client will not receive a response.
- Modifying the `scope` incorrectly: Can break downstream middleware or the application.
- Not handling exceptions: Unhandled errors will result in a 500 error for the client.
- Assuming access to Nexios-specific objects: Raw middleware only works with ASGI primitives.

By understanding and using raw ASGI middleware appropriately, you can extend your Nexios application with powerful, low-level features and integrate seamlessly with the broader ASGI ecosystem.
