# Request Models in Nexios

Request models are the backbone of robust, secure, and well-documented APIs. In Nexios, request models are built using Pydantic's `BaseModel`, which provides automatic validation, serialization, and OpenAPI integration.

---

## Why Use Request Models?

- **Automatic data validation**: Ensure incoming data matches your expectations.
- **Clear API documentation**: Models are reflected in your OpenAPI docs.
- **Type safety**: IDE autocompletion and fewer runtime errors.

---

## Defining Request Models

Request models are standard Pydantic models that define the expected structure of incoming request data. You can use them for POST, PUT, and PATCH endpoints, or any route that expects a JSON body.

```python
from nexios import NexiosApp
from pydantic import BaseModel

class UserCreateRequest(BaseModel):
    name: str
    age: int
    email: str

app = NexiosApp()

@app.post("/users", request_model=UserCreateRequest, summary="Create a new user")
async def create_user(req, res):
    data = req.body  # Already validated as UserCreateRequest
    # process user creation
    ...
```

![Request Body Example](./request-body.png)

---

## Advanced Usage

- Use nested models for complex payloads.
- Add field descriptions and examples for better docs:

```python
class Address(BaseModel):
    street: str
    city: str
    country: str

class UserWithAddress(BaseModel):
    name: str
    address: Address
```

---

## Best Practices

- Always validate incoming data with request models.
- Document required and optional fields.
- Use Pydantic features like validators, default values, and constraints.
- Keep models in a dedicated `models.py` for larger projects.

For more details on Pydantic models, see the [Pydantic documentation](https://pydantic-docs.helpmanual.io/).
