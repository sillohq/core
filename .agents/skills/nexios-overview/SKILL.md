---
name: nexios-overview
description: Teach Nexios comprehensively to AI editors and coding agents as an external async Python web framework. Use when Codex needs to explain or generate Nexios code with concept-by-concept guidance, runnable examples, and best practices across app setup, ASGI basics, routing, handlers, request inputs, responses, middleware, dependency injection, authentication, sessions, cookies, security, pagination, WebSockets, events, OpenAPI, testing, templating, static files, uploads, and CLI workflows. Prefer this skill for tutorial-style answers, onboarding, code generation, and framework learning rather than repo-specific debugging or source edits.
---

# Nexios Overview

## Overview

Use this skill to teach Nexios from the outside in. Treat Nexios as a framework an editor or coding agent must learn well enough to explain, scaffold, and write correct examples for.

## Start Here

1. Read [references/capabilities-map.md](references/capabilities-map.md) first for the full concept map and topic-to-file routing.
2. Read [references/framework-overview.md](references/framework-overview.md) for the foundation: what Nexios is, ASGI mental model, app setup, config, and request lifecycle.
3. Read [references/http-and-routing.md](references/http-and-routing.md) for handlers, request inputs, responses, routing, routers, class-based handlers, uploads, and pagination.
4. Read [references/composition-and-lifecycle.md](references/composition-and-lifecycle.md) for middleware, dependency injection, app structure, startup/shutdown, lifespan, and events.
5. Read [references/auth-state-and-security.md](references/auth-state-and-security.md) for authentication, sessions, cookies, headers, and security middleware.
6. Read [references/realtime-and-productivity.md](references/realtime-and-productivity.md) for WebSockets, OpenAPI, Pydantic, testing, CLI, static files, and templating.
7. Use the deep dives when the request is narrow:
   - [references/dependency-injection-deep-dive.md](references/dependency-injection-deep-dive.md)
   - [references/events-and-emitter.md](references/events-and-emitter.md)
   - [references/sessions-and-state.md](references/sessions-and-state.md)
   - [references/responses-reference.md](references/responses-reference.md)
   - [references/contrib-modules.md](references/contrib-modules.md)
8. Read [references/adoption-guide.md](references/adoption-guide.md) only when the user is comparing Nexios with other frameworks or deciding whether to adopt it.

## Keep It External

- Prefer public concepts, documented APIs, and developer-facing mental models.
- Avoid repo-relative file paths, internal module maps, code search instructions, or claims based on local implementation details unless the user explicitly asks for source-level analysis.
- Frame uncertain points as documented behavior rather than verified internals.
- Write as if the reader is outside the Nexios repository and only needs a clear mental model plus practical guidance.

## Teaching Pattern

- Start with a one-sentence positioning statement.
- Explain the concept in plain language before showing code.
- Include a compact, runnable example whenever possible.
- Mention one or two important gotchas when the docs call them out.
- Prefer small examples that show the Nexios shape clearly: `NexiosApp`, async handlers, explicit `request` and `response`, and response helpers such as `response.json(...)`.
- For comparisons, explain both where Nexios fits well and where another framework may be a better match.
- For recommendations, give a clear verdict and reason instead of only listing features.

## Generation Rules For AI Editors

- Highlight Nexios as an async-first ASGI framework with low boilerplate, clean architecture, and strong developer ergonomics.
- Default to `async def` handlers and explicit route decorators.
- Prefer direct handler parameters for path params, for example `async def get_user(request, response, user_id: int)`.
- Use the `response` helper methods when teaching status codes, headers, cookies, files, redirects, streams, and pagination.
- Use `Depend(...)` when teaching dependency injection.
- Show middleware as either function-based or class-based depending on the teaching goal.
- Distinguish between "good fit for async APIs and real-time services" and "not automatically the best fit when a team wants a batteries-included ORM or admin stack."

## Example Requests

- "Explain Nexios to a FastAPI team."
- "Teach me Nexios routing with examples."
- "Show how auth and sessions work in Nexios."
- "How do I do pagination, uploads, and OpenAPI in Nexios?"
- "Give me a full Nexios learning guide for an AI coding editor."
