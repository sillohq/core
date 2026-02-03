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

::: danger
`nexios.hooks` is not available in the current codebase. Use middleware instead.
:::

## Before and After Request (Middleware)

You can perform work before and after the handler by using middleware:

```python
from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()

async def logging_middleware(request: Request, response: Response, next_call):
    print(f"Before request: {request.method} {request.url}")
    result = await next_call()
    print(f"After request: {response.status_code}")
    return result

app.add_middleware(logging_middleware)

@app.get("/")
async def index(request, response):
    return response.json({"message": "Hello, world!"})
```

## Custom Decorators

You can still use Python decorators to wrap handlers:

```python
from functools import wraps

def custom_hook_decorator(hook_func):
    def decorator(handler_func):
        @wraps(handler_func)
        async def wrapper(request, response, *args, **kwargs):
            await hook_func(request, response)
            return await handler_func(request, response, *args, **kwargs)
        return wrapper
    return decorator

# Example usage
async def custom_hook(request, response):
    print("Custom hook executed")

@app.get("/example")
@custom_hook_decorator(custom_hook)
async def example_handler(request, response):
    return response.json({"message": "Custom hook in action"})
```
