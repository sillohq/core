# Response Models in Nexios

Response models describe the structure and content of the data your API returns. Nexios leverages Pydantic models for response validation and OpenAPI documentation, ensuring your API is both robust and clearly documented.

---

## Why Use Response Models?

- **Automatic serialization**: Ensures consistent, type-safe output.
- **Clear documentation**: Consumers know exactly what to expect.
- **Error handling**: Document all possible responses, not just 200 OK.

---

## Single Response Model (Default)

By default, Nexios documents a 200 response using the model you specify in the `responses` argument.

```python
from nexios import NexiosApp
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

app = NexiosApp()

@app.get("/users/{user_id}", responses=User, summary="Get a user by ID")
async def get_user(req, res, user_id: int):
    ...
```

![Single Response Example](./response.png)

---

## Multiple Response Models (Status Codes)

You can document multiple possible responses by passing a dictionary to `responses`, mapping status codes to models. This is essential for production APIs that may return errors or alternate results.

```python
from nexios import NexiosApp
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

class ErrorResponse(BaseModel):
    message: str
    code: int

app = NexiosApp()

@app.get(
    "/users/{user_id}",
    responses={200: User, 404: ErrorResponse, 401: ErrorResponse},
    summary="Get user or error details"
)
async def get_user(req, res, user_id: int):
    ...
```

![Multi-response Example](./multi-response.png)

---

## Returning Lists of Models

You can use `List[Model]` to document endpoints that return arrays of objects.

```python
from nexios import NexiosApp
from pydantic import BaseModel
from typing import List

class User(BaseModel):
    name: str
    age: int

app = NexiosApp()

@app.get("/users", responses={200: List[User]}, summary="Get all users")
async def list_users(req, res):
    ...
```

![List Response Example](./response-list.png)

---

## Best Practices

- Always document all possible responses (success, error, validation, etc.).
- Use descriptive model names and field descriptions.
- For error responses, include both a message and a code.
- Return lists for collections, not objects.

For advanced response customization (headers, examples, etc.), see the OpenAPI specification or Nexios advanced guides.
