---
title: Handler Hooks
description: Nexios provides a set of hooks that allow you to execute code at specific points in the request-response cycle. These hooks can be used to perform tasks such as authentication, logging, and error handling.
head:
  - - meta
    - property: og:title
      content: Handler Hooks
  - - meta
    - property: og:description
      content: Nexios provides a set of hooks that allow you to execute code at specific points in the request-response cycle. These hooks can be used to perform tasks such as authentication, logging, and error handling.
---
# Handler Hooks `deprecated`

::: danger 🚨Warning
Handler hooks are deprecated and will be removed in a future release. Use middleware instead.
:::

## before_request

The `before_request` hook is executed before the request is processed. It can be used to perform authentication, log the request, or modify the request object.

Example:

```python
from nexios import NexiosApp
from nexios.hooks import before_request

app = NexiosApp()

async def handle_before_request(request, response):
    print(f"Before request: {request.method} {request.url}")
@app.get("/")
@before_request(handle_before_request)
async def index(request, response):
    return {"message": "Hello, world!"}
```

::: info 💡Tip

The befpre request handler must take the requets and response arguments

:::

## `after_request`

The `after_request` hook is executed after the request is processed. It can be used to perform logging, error handling, or modify the response object.

Note : the after request handler can not modify the outgoing response.

Example:

```python
from nexios import NexiosApp
from nexios.hooks import after_request

app = NexiosApp()

async def handle_after_request(request, response):
    print(f"After request: {response.status_code}")

@app.get("/")
@after_request(handle_after_request)
async def index(request, response):
    return {"message": "Hello, world!"}
```

## `Custom Hooks using python decorators`

Nexios also allows you to create custom hooks using python decorators.

Example:
from functools import wraps
```python
def custom_hook_decorator(hook_func):
    def decorator(handler_func):
        @wraps(handler_func)
        async def wrapper(request, response, *args, **kwargs):
            await hook_func(request, response)  # Execute custom hook
            return await handler_func(request, response, *args, **kwargs)
        return wrapper
    return decorator

# Example usage
async def custom_hook(request, response):
    print("Custom hook executed")

@app.get("/example")
@custom_hook_decorator(custom_hook)
async def example_handler(request, response):
    return {"message": "Custom hook in action"}

```

