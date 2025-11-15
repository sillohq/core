# Documenting Request Parameters in Nexios

Request parameters are essential for making your API flexible, filterable, and powerful. Nexios supports three main types of request parameters: path parameters, query parameters, and headers. This guide explains how to document each type in your OpenAPI docs, with clear examples and best practices.

---

## Path Parameters

Path parameters are part of the URL and are used to identify specific resources. Nexios automatically detects and documents path parameters in your routes.

```python
from nexios import NexiosApp

app = NexiosApp()

@app.get("/users/{user_id}", summary="Get a user by ID")
async def get_user(req, res, user_id: int):
    """Fetch a user by their unique ID."""
    ...
```

![Path Parameter Example](./path-params.png)

::: tip Best Practice
Always use type hints for path parameters. This ensures correct OpenAPI documentation and better developer experience.
:::

---

## Query Parameters

Query parameters are used for filtering, sorting, or pagination. Nexios does not auto-detect query parameters, but you can explicitly document them using the `parameters` argument.

```python
from nexios import NexiosApp
from nexios.openapi.models import Query

app = NexiosApp()

@app.get(
    "/users",
    parameters=[
        Query(name="user_id", description="Filter by user ID", required=False),
        Query(name="user_type", description="Filter by user type", required=False),
        Query(name="limit", description="Number of results to return", required=False)
    ],
    summary="List users with optional filters"
)
async def list_users(req, res):
    user_id = req.query_params.get("user_id")
    user_type = req.query_params.get("user_type")
    limit = req.query_params.get("limit", 10)
    ...
```

![Query Parameter Example](./query-params.png)

---

## Header Parameters

Headers are used for authentication tokens, custom client information, and more. Document them using the `Header` model.

```python
from nexios import NexiosApp
from nexios.openapi.models import Header

app = NexiosApp()

@app.get(
    "/users",
    parameters=[Header(name="X-Auth-Token", description="Access token", required=True)],
    summary="List users (requires authentication)"
)
async def list_users(req, res):
    token = req.headers.get("X-Auth-Token")
    ...
```

![Header Parameter Example](./headers.png)

---

## Best Practices

- Always document every parameter your endpoint expects.
- Use descriptive names and provide clear descriptions.
- Mark parameters as required or optional as appropriate.
- Use consistent naming conventions for headers and query params.

For more advanced parameter types (enums, arrays, etc.), see the OpenAPI specification or the Nexios advanced guides.
