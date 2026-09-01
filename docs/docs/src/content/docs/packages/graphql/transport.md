---
title: HTTP Transport
description: GraphQL over HTTP done to spec — content negotiation, correct status codes, GET queries, batching and file uploads.
---

The specification is mostly a set of rules about when the answer is 200 and
when it is 400. The framework's old module answered "always 200", including for
a document that failed to parse.

## Content negotiation

Two response media types, chosen from `Accept`.

**`application/json`** — the legacy shape every existing client understands.
Chosen by default, and for a client that says `*/*` or nothing.

**`application/graphql-response+json`** — the specification's own. A client
sending this is asking to be told about failures with status codes.

Under both, the rule this package applies is the same and is worth stating
plainly: **a request that never reached execution carries a real status; errors
produced by an operation that did run are a 200.**

| | |
|---|---|
| Body is not JSON | 400 |
| No document in the request | 400 |
| Document fails to parse or validate | 400 |
| Over the [cost budget](/packages/graphql/limits/) | 400 |
| Introspection when it is off | 403 |
| Mutation over `GET` | 405 |
| Body over `max_body` | 413 |
| Unsupported content type | 415 |
| A field resolver failed | **200**, with `errors` |

The last line is the one clients depend on, and it is preserved. The rest is
the difference between "your request was understood and something went wrong"
and "your request was not a request" — which the legacy always-200 shape makes
a client parse a body to discover.

## Requests

```python
from sillo.graphql import Transport

Graph(schema, transport=Transport(
    get_queries=True,
    batch=10,
    graphql_content_type=True,
    response_content_type=True,
    max_body="1MB",
))
```

### POST

`application/json` with `query`, and optionally `variables`, `operationName`
and `extensions`. Also accepted:

- **`application/graphql`** — the whole body is the document;
- **`application/x-www-form-urlencoded`** — `query` and JSON-encoded
  `variables`.

### GET

```
GET /graphql?query={hello}&variables={"n":1}
```

**Mutations are refused over `GET` with a 405**, whatever the configuration
says. The method is defined as safe, and a mutation reachable by following a
link, prefetching a URL or replaying a cache entry is a bug waiting for a
crawler.

`GET` is what makes a response cacheable at the edge. Combined with
[trusted documents](/packages/graphql/persisted/), where the set of possible
requests is finite and known, it is the configuration that lets a CDN sit in
front of a GraphQL endpoint at all.

Set `get_queries=False` to refuse it entirely.

### Batching

```json
[ { "query": "{ a }" }, { "query": "{ b }" } ]
```

An array of operations, answered with an array of results in the same order.

Capped at `batch` and executed **sequentially**. A batch is a work multiplier
arriving as one request, so running it concurrently would let a client turn one
connection into as many as it likes. `batch=0` refuses batches.

Each operation is measured against the limits individually, and one failing
does not stop the rest — its entry carries the errors.

## Uploads

The GraphQL multipart request specification. **Off by default**: an endpoint
that accepts files has a materially larger attack surface than one that does
not, and that should be a decision.

```python
from sillo.graphql import Uploads

Graph(schema, uploads=Uploads(
    enabled=True,
    max_size="10MB",
    max_files=10,
    max_total="50MB",
    content_types=("image/*", "application/pdf"),
))
```

A request carries three parts: `operations` (the JSON body, with `null` where
files go), `map` (file name → variable paths), and the files themselves.

```
operations: {"query":"mutation($f: Upload!){ upload(file: $f) }",
             "variables":{"f":null}}
map:        {"0":["variables.f"]}
0:          <the file>
```

Limits are checked **before** the contents are walked: a request over the file
count is refused without reading it. Paths support list indices
(`variables.files.0`), and one file may be mapped to several places.

`content_types` accepts exact types and family globs. A file the allow-list
does not cover is a 400 naming the file and its type.

## Body size

`max_body` caps the request before it is parsed. It is validated when the
`Transport` is constructed, so a typo is a configuration error at import rather
than a 500 on the first large request.

## The explorer

```python
from sillo.graphql import IDE

Graph(schema, ide=True)                                  # bundled, offline
Graph(schema, ide=IDE(enabled=True, assets="cdn"))       # GraphiQL from unpkg
```

**Off by default.** The old module served it at your production URL unless you
remembered otherwise, alongside introspection.

The bundled explorer is one HTML document with its CSS and JavaScript inline:
no network requests, no build step, works offline and under a
Content-Security-Policy that forbids third-party script. An editor, variables,
headers, a response pane and a schema browser.

It is served on `GET` only when the client asks for `text/html`, so a `GET`
query still executes and a browser still gets the page.

The page offers a subscriptions socket only when one is actually mounted.

## Auth and middleware

The route's own gate, rather than a check inside every resolver:

```python
Graph(schema, auth=Bearer(), middleware=[RateLimit(per_minute=60)])
```

Both pass through to the `Route`. Per-field checks remain available through
`@field(auth=...)` — see [Resolvers](/packages/graphql/resolvers/).

## OpenAPI

The endpoint is excluded from the OpenAPI document. The old module appeared
there as `GET /graphql → {"example": "This is an example response"}`, which
described neither what it accepts nor what it returns. The schema is the
documentation for a GraphQL endpoint.

## Mounting under a prefix

```python
api = Router(prefix="/api")
Graph(schema).mount(api)
app.mount_router(api)
```

`mount` takes a `SilloApp` or a `Router`.
