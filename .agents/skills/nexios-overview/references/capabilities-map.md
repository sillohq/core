# Nexios Concept Map

Use this file first. It is the routing table for the rest of the skill.

## Table of Contents

1. [How to Use This Skill](#how-to-use-this-skill)
2. [Full Topic Coverage](#full-topic-coverage)
3. [Which Reference to Read](#which-reference-to-read)
4. [Teaching Defaults for AI Editors](#teaching-defaults-for-ai-editors)

## How to Use This Skill

If the request is broad, read the files in this order:

1. [framework-overview.md](framework-overview.md)
2. [http-and-routing.md](http-and-routing.md)
3. [composition-and-lifecycle.md](composition-and-lifecycle.md)
4. [auth-state-and-security.md](auth-state-and-security.md)
5. [realtime-and-productivity.md](realtime-and-productivity.md)

If the request is narrow, jump straight to the matching section below.

## Full Topic Coverage

This skill is meant to cover the main public Nexios concepts that an AI editor should know how to explain and generate code for:

- What Nexios is and where it fits
- ASGI basics and the request lifecycle
- App setup and configuration
- Handlers and request or response flow
- Routing decorators, typed path params, `Route`, and `Router`
- Request inputs: JSON, forms, files, and streams
- Response types: JSON, text, HTML, files, redirects, streams
- Middleware and request state
- Dependency injection with `Depend(...)`
- App-level and router-level dependencies
- Startup, shutdown, lifespan, and events
- Authentication and protected routes
- Sessions, cookies, and headers
- Security middleware and production-oriented protections
- Pagination strategies
- WebSockets and real-time patterns
- OpenAPI and request or response schemas
- Pydantic integration
- Testing with the test client
- CLI workflows
- Static files and templating
- Upload handling

## Which Reference to Read

### Foundations

Read [framework-overview.md](framework-overview.md) for:

- Positioning Nexios
- ASGI mental model
- First app example
- Config and app setup
- Request lifecycle

### HTTP and Routing

Read [http-and-routing.md](http-and-routing.md) for:

- Handlers
- Request inputs
- Responses
- Decorator routing
- `Route` and `Router`
- Class-based handlers
- Uploads
- Pagination

### Composition and Lifecycle

Read [composition-and-lifecycle.md](composition-and-lifecycle.md) for:

- Middleware
- Dependency injection
- Shared dependencies
- Startup or shutdown hooks
- Lifespan
- Events

### Auth, State, and Security

Read [auth-state-and-security.md](auth-state-and-security.md) for:

- Authentication middleware
- Protected routes
- Sessions
- Cookies
- Headers
- Security middleware

Read [sessions-and-state.md](sessions-and-state.md) for:

- Detailed session setup
- Session backends
- Session expiry
- Cookie-backed state patterns

### Realtime and Productivity

Read [realtime-and-productivity.md](realtime-and-productivity.md) for:

- WebSockets
- OpenAPI
- Pydantic
- Testing
- CLI
- Static files
- Templating

### Deep Dives

Read [dependency-injection-deep-dive.md](dependency-injection-deep-dive.md) for:

- Context-aware DI
- Generator dependencies
- Class dependencies
- Shared app/router dependencies

Read [events-and-emitter.md](events-and-emitter.md) for:

- `app.events`
- Custom emitters
- One-time listeners
- Priority and namespaces

Read [responses-reference.md](responses-reference.md) for:

- Response object rules
- Response types
- Chaining patterns
- Headers and cookies on responses

Read [contrib-modules.md](contrib-modules.md) for:

- Redis integration
- Background tasks
- Mail
- Tortoise ORM

### Adoption and Comparison

Read [adoption-guide.md](adoption-guide.md) for:

- Framework comparisons
- Tradeoffs
- Adoption recommendations

## Teaching Defaults for AI Editors

When generating or explaining Nexios code:

- Use `NexiosApp()` as the default app entry point.
- Use `async def` handlers unless the docs explicitly suggest another pattern.
- Include both `request` and `response` parameters in teaching examples.
- Pass typed path params directly into the handler signature.
- Prefer small, runnable examples over large abstractions.
- Call out important documented gotchas, such as response-building order and middleware return requirements.
