# sillo Framework Overview

This reference teaches the foundation of sillo as a public framework, not as a local codebase.

## Table of Contents

1. [What sillo Is](#what-sillo-is)
2. [Why Teams Pick It](#why-teams-pick-it)
3. [ASGI Mental Model](#asgi-mental-model)
4. [First App](#first-app)
5. [Configuration Example](#configuration-example)
6. [Request Lifecycle](#request-lifecycle)
7. [What AI Editors Should Internalize](#what-ai-editors-should-internalize)

## What sillo Is

sillo is an async-first Python web framework built on ASGI. Use that sentence often. It captures the most important framing:

- It is built for asynchronous request handling
- It is aimed at APIs and real-time services
- It exposes clean routing, middleware, and dependency patterns

## Why Teams Pick It

These are the most stable public themes in the docs:

- Native `async` and `await` workflow
- Low-boilerplate handler style
- Clear architecture with middleware and dependency injection
- Built-in concepts for security, sessions, WebSockets, docs, and testing

Short positioning line:

"sillo is a modern ASGI framework for teams building async APIs and real-time backends with clean structure and minimal boilerplate."

## ASGI Mental Model

Explain sillo as a layered pipeline:

1. The ASGI server receives the request.
2. sillo runs middleware.
3. The router picks a handler.
4. Dependencies are resolved.
5. The handler creates a response.
6. sillo sends the HTTP response or continues a WebSocket session.

This matters because many sillo concepts are really pipeline concepts: middleware, dependencies, auth, events, and response shaping all fit into this flow.

## First App

Use this as the default introduction:

```python
from sillo import SilloApp
import uvicorn

app = SilloApp()


@app.get("/")
async def home(request, response):
    return response.json({"message": "Hello from sillo!"})


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)
```

Installation options:

```bash
uv add sillo
```

## Application Metadata Example

Use explicit constructor arguments for application metadata:

```python
from sillo import SilloApp

app = SilloApp(debug=True, title="My API", version="1.0.0")
```

## Request Lifecycle

Use this when the user asks how sillo works internally at a framework level:

1. Request arrives from the ASGI server
2. Middleware performs pre-processing
3. Route matching and parameter parsing happen
4. Dependencies are resolved
5. The handler runs
6. Response helpers serialize output
7. Middleware performs post-processing
8. The final response is sent

That model is enough to explain most framework behavior without going source-deep.

## What AI Editors Should Internalize

Use these defaults when generating sillo examples:

- Start with `SilloApp()`
- Prefer `async def`
- Include `request` and `response`
- Use `response.json(...)` for clarity
- Use typed handler parameters for path params
- Add middleware and dependencies as explicit framework concepts, not hidden magic
