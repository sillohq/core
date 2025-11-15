---
title: Class-Based Views
description: Class-Based Views in Nexios offer a structured and modular approach to handling HTTP requests.
head:
  - - meta
    - property: og:title
      content: Class-Based Views
  - - meta
    - property: og:description
      content: Class-Based Views in Nexios offer a structured and modular approach to handling HTTP requests.
---
# Class-Based Views

Class-Based Views in Nexios offer a structured and modular approach to handling HTTP requests. By encapsulating request logic within a class, developers can easily manage middleware, request preprocessing, error handling, and response formatting. The `APIHandler` class serves as the **base class** for creating class-based handlers, providing hooks for handling requests before execution, after execution, and error handling.


## Basic Usage

```python
from nexios.views import APIHandler
from nexios import NexiosApp
app = NexiosApp()
class UserView(APIHandler):
    async def get(self, request, response):
        user_id = request.state.user_id  # Retrieve stored state
        return response.json({"user_id": user_id})

app.add_route(UserView.as_route("/user"))
```

::: tip 💡Tip

`.as_route` can also take same argument as route `decorators` or Nexios `Route` class

:::

## Middleware Support

Class-Based Views in Nexios also support middleware functions. Middleware functions are executed in order, before the request reaches the handler method.

```python
from nexios.views import APIHandler
from nexios import NexiosApp
app = NexiosApp()
class UserView(APIHandler):
    async def get(self, request, response):
        user_id = request.state.user_id  # Retrieve stored state
        return response.json({"user_id": user_id})

    middlewares = [auth_middleware, logging_middleware]  # Pass middleware as a list

app.add_route(UserView.as_route("/user"))
```

## Middleware Execution Flow
When a request is made to a class-based view with middleware, the execution flow is as follows:

- Middleware Execution: Each middleware function in the middleware list is executed in sequence. Each middleware can modify the request or short-circuit the request by returning a response early.

- Handler Execution: Once all middleware functions have been executed, the request is passed to the appropriate handler method (get, post, etc.).

- Response Return: The response from the handler is returned to the client.