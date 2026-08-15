---
title: Exception Handlers
description: "Turning database errors into HTTP responses: the four bundled handlers, their status codes, registering them, and why the default detail should not be shipped as-is."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Exception Handlers
  - tag: meta
    attrs:
      property: og:description
      content: DoesNotExist, IntegrityError, ValidationError and OperationalError as HTTP responses.
---

Without a handler, a Tortoise error reaching the top of a handler is a 500. The
four below map the common ones onto the status codes they actually mean.

```python
from sillo.record.exceptions import register_db_exception_handlers

app = SilloApp()
register_db_exception_handlers(app)
```

## The four

| Exception | Status | Body |
| --- | --- | --- |
| `DoesNotExist` | `404` | `{"error": "Not Found", "detail": "…"}` |
| `IntegrityError` | `409` | `{"error": "Conflict", "detail": "…"}` |
| `ValidationError` | `422` | `{"error": "Validation Error", "detail": "…"}` |
| `OperationalError` | `503` | `{"error": "Service Unavailable", "detail": "Database unavailable"}` |

### `DoesNotExist` → 404

Raised by `.get()` when nothing matches.

```python
post = await Post.get(id=post_id)     # 404 if there is no such post
```

Which makes the handler-level shape pleasantly short, no `if post is None`
branch in every endpoint.

The alternative is [`get_or_none()`](/orm/models/#fetch-shortcuts) and an
explicit branch. Use that when absence is *not* a 404. When you want to return
an empty object, or a different message.

### `IntegrityError` → 409

Unique constraint violations, null constraint violations, foreign key
violations.

409 is right for the duplicate case: the request was well-formed, and conflicts
with the current state. It is less right for a null or FK violation, which is
usually a bug rather than a conflict, but the exception type does not
distinguish them, and 409 is the least-wrong single answer.

### `ValidationError` → 422

Tortoise's own field validation, a value too long for its column, a bad choice.

Most validation should never reach here. [Request
validation](/guides/validation/) runs before the handler and produces
field-level errors; this is the backstop for what gets past it.

### `OperationalError` → 503

Connection refused, timeout, network partition.

503 tells a load balancer and a monitoring system that the instance is
unhealthy rather than that the request was bad, which is what you want when the
database is down: shed load, do not retry the same broken request as if it were
the client's fault.

Note this one **does not** include the exception text. A connection error can
name hosts, ports and users, and none of that belongs in a public response
body.

## The other three do leak detail

```json
{ "error": "Conflict", "detail": "UNIQUE constraint failed: users.email" }
```

That is the driver's message, and it names your table and column. Sometimes
useful in development, and on a public API it hands out schema details for
free, and for a login or sign-up endpoint, a unique-violation message confirms
whether an address is registered.

Override them in production:

```python
from tortoise.exceptions import IntegrityError


async def handle_conflict(request, response, exc):
    logger.warning("integrity error", exc_info=exc)
    return response.json(
        {"error": "Conflict", "detail": "That value is already in use."},
        status_code=409,
    )


app.add_exception_handler(IntegrityError, handle_conflict)
```

Log the real message; return a generic one. `register_db_exception_handlers` is
a sensible default, not a security review.

## Registering selectively

The bundled function registers all four. To pick:

```python
from tortoise.exceptions import DoesNotExist, OperationalError
from sillo.record.exceptions import handle_does_not_exist, handle_operational_error

app.add_exception_handler(DoesNotExist, handle_does_not_exist)
app.add_exception_handler(OperationalError, handle_operational_error)
```

Each handler is a plain async function taking `(request, response, exc)`, the
same signature as any other [exception handler](/guides/error-handling/), so
they compose with your own and can be wrapped.

## Ordering

A handler registered for a subclass wins over one for its parent, so a specific
handler added later does not need the general one removed:

```python
app.add_exception_handler(IntegrityError, handle_conflict)
app.add_exception_handler(MyDuplicateEmailError, handle_duplicate_email)
```

## What is not covered

- **`DoesNotExist` from a legitimate lookup inside a service.** A 404 is right
  for "the URL names a row that does not exist"; it is wrong when a background
  job cannot find a related record. Catch it there.
- **Deadlocks and serialisation failures.** These arrive as `OperationalError`
  and become a 503, when the correct answer is usually a
  [retry](/orm/transactions/#concurrency).
- **Timeouts under load**, which look identical to a database being down.

The handlers are a floor. Anything with specific meaning in your application
deserves its own.
