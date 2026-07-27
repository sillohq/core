---
title: GraphQL Integration
description: Add GraphQL support to your sillo application using Strawberry GraphQL.
---

#  GraphQL Integration

Add GraphQL support to your sillo application using [Strawberry](https://strawberry.rocks/).

##  What is GraphQL?

GraphQL is a query language for APIs and a runtime for fulfilling those queries with your existing data. It provides a complete and understandable description of the data in your API, gives clients the power to ask for exactly what they need and nothing more, makes it easier to evolve APIs over time, and enables powerful developer tools.

`sillo.graphql` provides:

- **Strawberry Integration**: Seamless integration with the Strawberry GraphQL library.
- **GraphiQL Interface**: Built-in interactive in-browser GraphQL IDE.
- **Async Support**: Full support for async resolvers.

##  Installation

GraphQL support ships with sillo as a first-party module. Install with the graphql extra:

```bash
uv add "sillo[graphql]"
```

This installs `strawberry-graphql` alongside sillo.

##  Quick Start

###  Basic Server Setup

Here is a simple example of how to set up a GraphQL server with sillo:

```python
import strawberry
from sillo import silloApp
from sillo.graphql import GraphQL

# 1. Define your schema using Strawberry
@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello World"

schema = strawberry.Schema(query=Query)

# 2. Create your sillo app
app = silloApp()

# 3. Instantiate the GraphQL handler
# By default, this mounts the GraphQL endpoint at /graphql
# and enables the GraphiQL interface.
GraphQL(app, schema)

# 4. Run the app
if __name__ == "__main__":
    app.run()
```

Now you can visit `http://localhost:8000/graphql` to see the GraphiQL interface and execute queries.

###  Example Query

In the GraphiQL interface, you can run the following query:

```graphql
query {
  hello
}
```

Response:

```json
{
  "data": {
    "hello": "Hello World"
  }
}
```

##  Configuration

The `GraphQL` class accepts the following arguments:

- `app` (silloApp): The sillo application instance.
- `schema` (strawberry.Schema): The Strawberry schema to use.
- `path` (str, optional): The path to mount the GraphQL endpoint. Defaults to `/graphql`.
- `graphiql` (bool, optional): Whether to enable the GraphiQL interface. Defaults to `True`.

###  Custom Path

You can change the path where the GraphQL endpoint is mounted:

```python
GraphQL(app, schema, path="/api/graphql")
```

###  Disabling GraphiQL

For production environments, you might want to disable the GraphiQL interface:

```python
GraphQL(app, schema, graphiql=False)
```

##  Async Resolvers

sillo fully supports async resolvers in Strawberry.

```python
@strawberry.type
class Query:
    @strawberry.field
    async def user(self, id: strawberry.ID) -> User:
        # Fetch user from database asynchronously
        return await db.get_user(id)
```

##  Context

The `request` and `response` objects are available in the GraphQL context.

```python
@strawberry.type
class Query:
    @strawberry.field
    def user_agent(self, info) -> str:
        request = info.context["request"]
        return request.headers.get("user-agent", "Unknown")
```

##  How a query is handled

`GraphQL(app, schema)` registers a single `Route` at `path` (default `/graphql`) accepting `GET` and `POST`:

- **`GET`** — when `graphiql=True` (default) returns the GraphiQL IDE HTML; when disabled returns `404`.
- **`POST`** — reads the JSON body, expects an object with `query`, optional `variables`, and optional `operationName`, then runs `schema.execute` with a context of `{"request", "response"}`. Invalid JSON or a non-object body returns `400` with an `errors` payload.

The schema is executed asynchronously, so resolver `await`s run on the event loop like any other sillo handler.

##  Testing

Drive queries through `TestClient` with a `POST` of a JSON `{"query": ...}` body:

```python
import strawberry
from sillo import silloApp
from sillo.graphql import GraphQL
from sillo.testclient import TestClient


@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello World"


schema = strawberry.Schema(query=Query)
app = silloApp()
GraphQL(app, schema)
client = TestClient(app)


def test_graphql_query():
    resp = client.post("/graphql", json={"query": "{ hello }"})
    assert resp.status_code == 200
    assert resp.json()["data"] == {"hello": "Hello World"}


def test_invalid_json_body():
    resp = client.post("/graphql", content=b"not json", headers={"content-type": "application/json"})
    assert resp.status_code == 400
```

For resolvers that hit the database, use your normal async fixtures in the test app — the `request`/`response` context flows through `schema.execute` unchanged.

##  Errors and edge cases

- **Malformed body** — a non-JSON or non-object `POST` yields `400` with `{"errors": [...]}`. GraphiQL itself is unaffected (it uses `GET`).
- **GraphiQL in production** — leaving `graphiql=True` exposes an in-browser IDE. Set `graphiql=False` for production endpoints you don't want browsable.
- **Auth** — `GraphQL` does not enforce authentication. Protect the route by registering auth middleware or checking `info.context["request"]` inside resolvers.
- **Extra dependency** — `strawberry-graphql` is required. Install with `uv add "sillo[graphql]"` (or your lockfile equivalent); importing `sillo.graphql` without it raises at runtime.

##  Related topics

- [Request Inputs](/guides/request-inputs/) — JSON body parsing used by the `POST` handler
- [Authentication](/guides/authentication/) — protecting the `/graphql` route
- [Middleware](/guides/middleware/) — ordering auth before the GraphQL route
