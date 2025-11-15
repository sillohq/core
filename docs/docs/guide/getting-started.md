---
icon: down-to-line
title: Getting Started with Nexios
description: Welcome to Nexios! This comprehensive guide will walk you through everything you need to know to get started with Nexios, a modern, async-first Python web framework designed for high-performance applications.
head:
  - - meta
    - property: og:title
      content: Getting Started with Nexios
  - - meta
    - property: og:description
      content: Welcome to Nexios! This comprehensive guide will walk you through everything you need to know to get started with Nexios, a modern, async-first Python web framework designed for high-performance applications.
---
# 🚀 What is Nexios?

Nexios is a cutting-edge Python web framework that combines the best of modern web development practices with exceptional performance. Built on ASGI (Asynchronous Server Gateway Interface), Nexios provides a clean, intuitive API that makes building scalable web applications straightforward and enjoyable.

### Key Features

- **🚀 High Performance**: Built on ASGI for exceptional speed and concurrency
- **🔄 Async-First**: Native async/await support throughout the framework
- **🛡️ Type Safe**: Full type hint support for better development experience
- **📚 Developer Friendly**: Intuitive API with excellent documentation
- **🔧 Production Ready**: Built-in security, testing, and deployment features
- **🎯 Flexible**: Extensive customization options for any use case
- **📖 OpenAPI Ready**: Automatic API documentation generation
- **🔌 Extensible**: Easy to add custom functionality and middleware

### Why Choose Nexios?

Nexios stands out from other Python web frameworks for several reasons:

**Performance**: Unlike traditional WSGI frameworks, Nexios leverages ASGI to handle thousands of concurrent connections efficiently. This means your application can serve more users with fewer resources.

**Simplicity**: The API is designed to be intuitive and easy to learn. You can start building applications quickly without getting lost in complex abstractions.

**Modern Python**: Nexios fully embraces modern Python features like type hints, async/await, and dataclasses, making your code more maintainable and less error-prone.

**Production Features**: Built-in support for authentication, CORS, rate limiting, and other production-ready features means you can focus on your business logic rather than infrastructure concerns.

## 📋 Prerequisites

Before you begin with Nexios, ensure you have the following:

### System Requirements

- **Python 3.9 or higher** - Nexios requires modern Python features
- **pip, poetry, or uv** - For package management
- **Basic understanding of async/await** - While not strictly required, it helps


| Feature                                                                     | Supported in |
| ---------------------------------------------------------------------------- | ------------ |
| Type annotations with generics                                                | 3.9+         |
| Async context managers                                                       | 3.7+         |
| Pattern matching                                                             | 3.10+        |
| Union types and other type system improvements                               | 3.9+         |
| Better async/await support                                                   | 3.7+         |


### ⚡ Async/Await Fundamentals

If you're new to async/await in Python, here are the key concepts you'll encounter:

- `async def`: Defines an asynchronous function that can be awaited
- `await`: Waits for an async operation to complete without blocking
- `async with`: Asynchronous context manager for resource management
- `async for`: Asynchronous iteration over async iterables

Nexios uses async/await extensively for handling concurrent requests efficiently. Don't worry if this is new to you - we'll cover it in detail throughout the documentation.


## 📦 Installation

Nexios can be installed using any Python package manager. We recommend using `uv` for the fastest and most reliable experience.

### Recommended: Using uv

[uv](https://github.com/astral-sh/uv) is a modern Python package manager that's significantly faster than traditional tools. It's a drop-in replacement for pip, pip-tools, and virtualenv.

::: code-group
```bash [Install uv]
# Install uv globally
pip install uv

# Create a new project directory
mkdir my-nexios-app
cd my-nexios-app

# Create a virtual environment and install Nexios
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install nexios
```

```bash [Alternative: Direct installation]
# Install uv and Nexios in one command
uv init my-nexios-app
cd my-nexios-app
uv add nexios
```
:::

### Alternative Package Managers

::: code-group
```bash [pip]
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Nexios
pip install nexios
```

```bash [poetry]
# Create a new project
poetry new my-nexios-app
cd my-nexios-app

# Add Nexios
poetry add nexios

# Activate environment
poetry shell
```

```bash [pipenv]
# Create a new project directory
mkdir my-nexios-app
cd my-nexios-app

# Initialize project
pipenv install nexios

# Activate environment
pipenv shell
```


| Package Manager  | Fastest Installation | Virtual Environment | Compatible with pip | Production | Written in Rust |
|------------------|---------------------|--------------------|--------------------|------------|----------------|
| uv (Recommended) | ⚡                   | 🔧                  | 🔄                  | 🚀         | ✅            |
| pip              | 🐌                   | ✅                  | ✅                  | ✅         |                |
| poetry           |                     | ✅                  |                     | ✅         |                |
| pipenv           |                     | ✅                  | ✅                  | ✅         |                |

::: tip Virtual Environments
Always use virtual environments to isolate your project dependencies. This prevents conflicts between different projects and keeps your system Python clean.

**Benefits of virtual environments:**
- 🛡️ Isolate project dependencies
- 🚫 Avoid version conflicts
- 📤 Easy project sharing and deployment
- 🧹 Clean system Python installation
- 🔄 Reproducible builds

**Creating virtual environments:**
```bash
# With uv (recommended)
uv venv

# With venv (built-in)
python -m venv venv

# With virtualenv
virtualenv venv
```
:::

## 🛠️ Your First Nexios Application

Now that you have Nexios installed, let's create your first application. We'll start with a simple example and gradually build up to more complex features.

### Basic Application

Create a file named `main.py`:

```python
from nexios import NexiosApp
import uvicorn 

# Create a new Nexios application
app = NexiosApp()

# Define a simple route
@app.get("/")
async def hello_world(request, response):
    return response.json({
        "message": "Hello from Nexios!",
        "status": "success"
    })

# If you forget to use async def for your handler, Nexios will run the handler in a threadpool

# If you define two routes with the same path and method, Nexios will raise a conflict error at startup.

# Run the application
if __name__ == "__main__":
    uvicorn.run("main:app")
```

### Running Your Application

You can run your Nexios application in several ways:

::: code-group
```bash [Direct execution]
python main.py
```

```bash [Nexios CLI (Requires Click)]
nexios run --reload
```
```bash [With uvicorn (recommended)]
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

```bash [With hypercorn]
hypercorn main:app --reload --bind 127.0.0.1:8000
```
:::

::: tip Development Server
For development, we recommend using `uvicorn` with the `--reload` flag. This will automatically restart your application when you make changes to your code.

**Benefits of uvicorn:**
- 🔄 Auto-reload on code changes
- ⚡ Fast startup time
- 🐛 Good error reporting
- 📊 Built-in logging
- 🔧 Easy configuration
:::

### Testing Your Application

Once your application is running, you can test it by opening your browser and navigating to `http://localhost:8000/docs`.

nexios provide an intaractive  API documentation interface. This allows you to test your API endpoints and explore the available routes.

## 🔍 Understanding the Code

Let's break down what's happening in our first application:

### 1. Application Creation

```python
from nexios import NexiosApp

app = NexiosApp()
```

- `NexiosApp()` creates a new web application instance
- This instance will handle all incoming HTTP requests
- It's configured with sensible defaults for development

### 2. Route Definition

```python
@app.get("/")
async def hello_world(request, response):
    return response.json({
        "message": "Hello from Nexios!",
        "status": "success"
    })

# If you forget to return a response, Nexios will raise an error indicating the handler did not return a response object.
```

- `@app.get("/")` decorates a function to handle GET requests to the root path
- The function must be `async` - this is a strict requirement in Nexios
- `request` and `response` are automatically provided by Nexios
- `response.json()` creates a JSON response with the specified data

### 3. Application Execution

```python
if __name__ == "__main__":
    app.run()

# If you run this in production, make sure to use uvicorn or another ASGI server for better performance and reliability.
```


## 🎯 Next Steps

Congratulations! You've successfully created and run your first Nexios application. Here's what you can explore next:

| Section                                                                           | Description                                                                                                                                                                                                                                                      |
|----------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [Routing Fundamentals](/guide/routing)                           | Learn how to create different types of routes and handle various HTTP methods:<br>- [HTTP Methods](/guide/routing#http-methods)<br>- [Path Parameters](/guide/routing#path-parameters)                                                                        |
| [Request and Response Handling](/guide/request-info)             | Understand how to work with incoming requests and outgoing responses:<br>- [Request Information](/guide/request-info)<br>- [Sending Responses](/guide/sending-responses)<br>- [Request Inputs](/guide/request-inputs) |
| [Core Concepts](/guide/concepts)                                | Dive deeper into Nexios architecture and concepts:<br>- [Framework Architecture](/guide/concepts)<br>- [Async Python](/guide/async-python)<br>- [Configuration](/guide/configuration)                                            |
| [Advanced Features](/guide/middleware)                           | Explore more advanced features as you become comfortable with the basics:<br>- [Middleware](/guide/middleware)<br>- [Authentication](/guide/authentication)<br>- [WebSockets](/guide/websockets)<br>- [Templating](/guide/templating) |

## ❓ Common Questions

### Why do all handlers need to be async?

Nexios is built on ASGI, which requires async handlers for optimal performance. Async handlers allow Nexios to handle multiple requests concurrently without blocking, leading to better performance and scalability.

### Can I use synchronous code in my handlers?

While handlers themselves must be async, you can call synchronous functions within them. However, for I/O operations (database queries, HTTP requests, file operations), you should use async alternatives for better performance.

If you call a blocking (sync) function in an async handler, your app may hang or perform poorly. Use `run_in_executor` for heavy sync work:

```python
import asyncio

def blocking_task():
    # Some CPU-bound or blocking code
    ...

@app.get("/heavy")
async def heavy_route(request, response):
    result = await asyncio.get_running_loop().run_in_executor(None, blocking_task)
    return response.json({"result": result})
```

### What happens if I pass invalid input or miss a required parameter?

If a required parameter is missing or invalid, Nexios will return a 422 error:

```python
@app.get("/items/{item_id}")
async def get_item(request, response, item_id: int):
    return response.json({"item_id": item_id})

# GET /items/abc will return a 422 Unprocessable Entity
```

### What if my middleware fails?

If your middleware raises an exception, it will interrupt the request and return a 500 error. Use try/except in middleware for graceful error handling:

```python


async def failing_middleware(self, request, response, call_next):
    try:
        # Your logic here
        return await call_next()
    except Exception as exc:
        return response.json({"error": str(exc)}, status_code=500)

app.add_middleware(failing_middleware)
```

### What if I try to dynamically import a handler that doesn't exist?

If a dynamically imported handler does not exist or fails to import, Nexios will raise an ImportError at startup.

### What if my custom path converter fails?

If your custom converter raises a ValueError, Nexios will return a 422 error with your message.

### How does Nexios compare to FastAPI/Django/Flask?

Nexios offers a unique combination of simplicity and performance:
- **vs FastAPI**: Simpler API, less boilerplate, easier learning curve
- **vs Django**: Lighter weight, more flexible, better for APIs
- **vs Flask**: Async-first, better performance, modern Python features

### What's the difference between `app.run()` and using uvicorn directly?

`app.run()` is a convenience method that starts a development server. For production, you should use uvicorn, hypercorn, or another ASGI server directly for better control and performance.

## 🆘 Getting Help

If you run into issues or have questions:

1. **Check the documentation** - This guide and the other documentation pages
2. **Look at examples** - The `examples/` directory contains working code
3. **Search existing issues** - Check the GitHub repository for similar problems
4. **Ask the community** - Join discussions on GitHub or other forums

Remember, everyone starts somewhere! Don't hesitate to ask questions and experiment with the code. The Nexios community is here to help you succeed.

---

Now that you have the basics down, let's explore more advanced features. Start with the [Routing Guide](/guide/routing) to learn how to create more complex applications, or jump into [Core Concepts](/guide/concepts) to understand how Nexios works under the hood.


