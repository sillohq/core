# GraphQL Integration

Add GraphQL support to your Nexios application using [Strawberry](https://strawberry.rocks/).

## What is GraphQL?

GraphQL is a query language for APIs and a runtime for fulfilling those queries with your existing data. It provides a complete and understandable description of the data in your API, gives clients the power to ask for exactly what they need and nothing more, makes it easier to evolve APIs over time, and enables powerful developer tools.

This contrib provides:

- **Strawberry Integration**: Seamless integration with the Strawberry GraphQL library.
- **GraphiQL Interface**: Built-in interactive in-browser GraphQL IDE.
- **Async Support**: Full support for async resolvers.

## Installation

The GraphQL contrib is included with the main `nexios_contrib` package.

```bash
pip install nexios_contrib
```

You will also need to install `strawberry-graphql`:

```bash
pip install strawberry-graphql
```

## Quick Start

### Basic Server Setup

Here is a simple example of how to set up a GraphQL server with Nexios:

```python
import strawberry
from nexios import NexiosApp
from nexios_contrib.graphql import GraphQL

# 1. Define your schema using Strawberry
@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello World"

schema = strawberry.Schema(query=Query)

# 2. Create your Nexios app
app = NexiosApp()

# 3. Add the GraphQL plugin
# By default, this mounts the GraphQL endpoint at /graphql
# and enables the GraphiQL interface.
GraphQL(app, schema)

# 4. Run the app
if __name__ == "__main__":
    app.run()
```

Now you can visit `http://localhost:8000/graphql` to see the GraphiQL interface and execute queries.

### Example Query

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

## Configuration

The `GraphQL` class accepts the following arguments:

- `app` (NexiosApp): The Nexios application instance.
- `schema` (strawberry.Schema): The Strawberry schema to use.
- `path` (str, optional): The path to mount the GraphQL endpoint. Defaults to `/graphql`.
- `graphiql` (bool, optional): Whether to enable the GraphiQL interface. Defaults to `True`.

### Custom Path

You can change the path where the GraphQL endpoint is mounted:

```python
GraphQL(app, schema, path="/api/graphql")
```

### Disabling GraphiQL

For production environments, you might want to disable the GraphiQL interface:

```python
GraphQL(app, schema, graphiql=False)
```

## Async Resolvers

Nexios fully supports async resolvers in Strawberry.

```python
@strawberry.type
class Query:
    @strawberry.field
    async def user(self, id: strawberry.ID) -> User:
        # Fetch user from database asynchronously
        return await db.get_user(id)
```

## Context

The `request` and `response` objects are available in the GraphQL context.

```python
@strawberry.type
class Query:
    @strawberry.field
    def user_agent(self, info) -> str:
        request = info.context["request"]
        return request.headers.get("user-agent", "Unknown")
```
