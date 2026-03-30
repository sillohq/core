# Nexios Framework Overview

This reference teaches the foundation of Nexios as a public framework, not as a local codebase.

## Table of Contents

1. [What Nexios Is](#what-nexios-is)
2. [Why Teams Pick It](#why-teams-pick-it)
3. [ASGI Mental Model](#asgi-mental-model)
4. [First App](#first-app)
5. [Configuration Example](#configuration-example)
6. [Request Lifecycle](#request-lifecycle)
7. [What AI Editors Should Internalize](#what-ai-editors-should-internalize)

## What Nexios Is

Nexios is an async-first Python web framework built on ASGI. Use that sentence often. It captures the most important framing:

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

"Nexios is a modern ASGI framework for teams building async APIs and real-time backends with clean structure and minimal boilerplate."

## ASGI Mental Model

Explain Nexios as a layered pipeline:

1. The ASGI server receives the request.
2. Nexios runs middleware.
3. The router picks a handler.
4. Dependencies are resolved.
5. The handler creates a response.
6. Nexios sends the HTTP response or continues a WebSocket session.

This matters because many Nexios concepts are really pipeline concepts: middleware, dependencies, auth, events, and response shaping all fit into this flow.

## First App

Use this as the default introduction:

```python
from nexios import NexiosApp
import uvicorn

app = NexiosApp()

@app.get("/")
async def home(request, response):
    return response.json({"message": "Hello from Nexios!"})

if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)
```

Installation options:

```bash
pip install nexios
```

```bash
uv pip install nexios
```

## Configuration Example

Use configuration when teaching that Nexios scales beyond a toy app:

```python
from nexios import NexiosApp, MakeConfig

config = MakeConfig({
    "debug": True,
    "allowed_hosts": ["localhost", "example.com"]
})

app = NexiosApp(
    config=config,
    title="My API",
    version="1.0.0"
)
```

Key idea: Nexios supports explicit configuration without forcing a large project skeleton.

## Request Lifecycle

Use this when the user asks how Nexios works internally at a framework level:

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

Use these defaults when generating Nexios examples:

- Start with `NexiosApp()`
- Prefer `async def`
- Include `request` and `response`
- Use `response.json(...)` for clarity
- Use typed handler parameters for path params
- Add middleware and dependencies as explicit framework concepts, not hidden magic
