---
title: Errors
description: Free builders with stable codes, masking of anything unexpected, and mapping your own exceptions onto GraphQL errors.
---

`sillo` builds responses with free functions — `json()`, `text()`,
`redirect()`. Errors here follow the same shape.

```python
from sillo.graphql import forbidden, not_found


@field
async def post(ctx: HttpContext, id: int) -> Post:
    found = await Post.objects.get_or_none(id=id)
    if found is None:
        raise not_found("No such post")
    if not found.visible_to(ctx.user):
        raise forbidden("You cannot see this post")
    return found
```

```json
{
  "errors": [{
    "message": "No such post",
    "path": ["post"],
    "extensions": { "code": "NOT_FOUND" }
  }]
}
```

## The builders

| | code | HTTP |
|---|---|---|
| `unauthenticated(message)` | `UNAUTHENTICATED` | 401 |
| `forbidden(message)` | `FORBIDDEN` | 403 |
| `not_found(message)` | `NOT_FOUND` | — |
| `bad_input(message)` | `BAD_USER_INPUT` | — |
| `conflict(message)` | `CONFLICT` | — |
| `too_many_requests(message, retry_after=)` | `TOO_MANY_REQUESTS` | — |
| `internal(message)` | `INTERNAL_SERVER_ERROR` | — |

Keyword arguments become extensions:

```python
raise not_found("No such post", id=id)
raise too_many_requests(retry_after=30)
```

```json
{ "extensions": { "code": "NOT_FOUND", "id": 42 } }
```

Codes are a closed set because they are what clients branch on. A client that
sees `FORBIDDEN` can offer a login; one that sees free text can only display
it.

## Masking

**An exception that escapes a resolver is masked.** What it said may name a
host, a table or a credential.

```python
@field
async def report(ctx: HttpContext) -> Report:
    raise RuntimeError("dsn=postgres://user:hunter2@10.0.0.5/db")
```

```json
{ "errors": [{ "message": "Unexpected error",
               "extensions": { "code": "INTERNAL_SERVER_ERROR" } }] }
```

The original is logged with its traceback, so it is not lost — only not sent.

Errors raised through the builders above are **never** masked. Raising one is a
deliberate statement about what went wrong, unlike a `KeyError` escaping a
resolver. Neither are validation errors: those are about the client's document
and are safe to pass on verbatim.

That distinction is the reason not to reach for a blanket "mask everything"
extension. Masking a depth-limit refusal or a "not found" makes an API
unusable; masking a `RuntimeError` is the whole point.

### Configuring it

```python
from sillo.graphql import ErrorPolicy

Graph(schema, errors=ErrorPolicy(
    mask=True,                          # the default
    mask_message="Unexpected error",
    include_stacktrace=False,           # development only
    correlation_key="requestId",
    log_masked=True,
))
```

`include_stacktrace` attaches the traceback to `extensions.stacktrace`. Never
turn it on in production; it is exactly the information masking exists to keep
back.

## Correlation

Every error carries the request id when there is one, read from
`x-request-id` or from the connection's own `request_id`:

```json
{ "extensions": { "code": "INTERNAL_SERVER_ERROR", "requestId": "01HQ...ZK" } }
```

That is what turns "it broke this morning" into one log line. Set
`correlation_key=None` to leave it out.

## Mapping your own exceptions

An application raises its own exceptions, and masking them is the right default
and a poor experience.

```python
from sillo.graphql import bad_input, conflict, not_found


@graph.on_error(RecordNotFound)
def _(exc):
    return not_found(str(exc))


@graph.on_error(IntegrityError)
def _(exc):
    return conflict("That value is already taken", field=exc.column)


@graph.on_error(ValidationError)
def _(exc):
    return bad_input(exc.message, field=exc.field)
```

The first registered mapping whose type matches wins. A hook that returns
`None` falls through to masking, which is a useful way to map only some
instances of a type.

Mapping keeps the exception's own class hierarchy: registering the base class
covers every subclass.

## The error tree

```
SilloGraphQLError          every failure this package raises
├── GraphQLError           an error a resolver means the client to see
│   └── GraphQLDenied      refused before execution; carries an HTTP status
├── ResolverError          a resolver could not be adapted (import time)
└── LoaderError            a batch function broke its contract
```

`except SilloGraphQLError` catches package failures without swallowing your
application's own.

## Status codes

Under the legacy `application/json` a field error is still a 200 — the
operation ran, and that is what clients expect. Failures *before* execution
carry a real status: 400 for a document that would not parse or validate, 405
for a mutation over `GET`, 403 for introspection when it is off.

Under `application/graphql-response+json` the same rules apply, which is the
specification's own behaviour. See
[HTTP Transport](/packages/graphql/transport/).

## Errors in subscriptions

An error while starting a subscription arrives as the protocol's `error`
message and ends the operation. An error from a value already streaming arrives
inside a `next` payload, and the stream continues — the same partial-response
rule as a query.
