---
title: Pydantic Integration
description: Nexios provides seamless integration with Pydantic, offering a flexible way to handle data validation and serialization. Unlike some frameworks that force you to use type hints, Nexios gives you the freedom to choose between dynamic typing and strict type validation.
head:
  - - meta
    - property: og:title
      content: Pydantic Integration
  - - meta
    - property: og:description
      content: Nexios provides seamless integration with Pydantic, offering a flexible way to handle data validation and serialization. Unlike some frameworks that force you to use type hints, Nexios gives you the freedom to choose between dynamic typing and strict type validation.
---
## ❓ Why Pydantic with Nexios?

- **Flexible Validation**: Use Pydantic when you need it, without being forced into a type-hinted architecture
- **Clean Error Handling**: Built-in error formatting that works out of the box
- **Performance**: Efficient validation with minimal overhead
- **Optional Typing**: Add type safety where it matters most

## 🚀 Getting Started

### Installation

First, install Pydantic:

```bash
pip install pydantic
```

### Basic Usage

```python
from nexios import NexiosApp
from pydantic import BaseModel
from datetime import datetime

app = NexiosApp()

class UserCreate(BaseModel):
    username: str
    email: str
    signup_date: datetime = None
    age: int = None

@app.post("/users")
async def create_user(request, response):
    # Manually validate with Pydantic
    data = await request.json
    user = UserCreate(**data)
    
    # Your business logic here
    return response.json(user.dict())
```

## ⚠️ Error Handling

Nexios provides a built-in error handler for Pydantic validation errors with multiple formatting options:

```python
from nexios.utils.pydantic import add_pydantic_error_handler

# Add the error handler to your app
add_pydantic_error_handler(app, style="list", status_code=422)
```

### Error Formats

Choose from three different error formats:

1. **Flat Format**
   ```json
   {
     "error": "Validation Error",
     "errors": {
       "username": "field required",
       "email": "invalid email format"
     }
   }
   ```

2. **List Format**
   ```json
   {
     "error": "Validation Error",
     "errors": [
       {"field": "username", "message": "field required"},
       {"field": "email", "message": "invalid email format"}
     ]
   }
   ```

3. **Nested Format** (default)
   ```json
   {
     "error": "Validation Error",
     "errors": {
       "user": {
         "username": "field required",
         "profile": {
           "email": "invalid email format"
         }
       }
     }
   }
   ```

## ⚡ Advanced Usage

### Nested Models

```python
class Profile(BaseModel):
    bio: str
    website: str = None

class UserUpdate(BaseModel):
    username: str
    profile: Profile

@app.put("/users/{user_id}")
async def update_user(request, response, user_id: str):
    data = await request.json
    update = UserUpdate(**data)
    # Update user logic here
    return response.json(update.dict())
```

### Custom Validators

```python
from pydantic import validator

class Item(BaseModel):
    name: str
    price: float
    
    @validator('price')
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be positive')
        return v
```

## 🎯 Why Nexios is More Flexible

1. **No Type Hinting Required**
   - Use Pydantic where it makes sense
   - Keep other parts of your application dynamic
   - Gradually adopt type safety as needed

2. **No Framework Lock-in**
   - Pydantic is optional, not enforced
   - Easy to remove or replace if needed
   - No tight coupling with the framework

3. **Progressive Enhancement**
   - Start simple, add validation later
   - Mix and match validation approaches
   - Evolve your codebase at your own pace

## ✅ Best Practices

1. Use Pydantic for:
   - API request/response validation
   - Configuration management
   - Data serialization/deserialization
   - Complex data transformations

2. Keep it simple when:
   - Building prototypes
   - Internal APIs
   - Simple endpoints

3. Consider using type hints for:
   - Public APIs
   - Critical business logic
   - Team projects with multiple developers

## 📁 Example Project Structure

```
myapp/
  models/
    __init__.py
    user.py      # Pydantic models
    schemas.py   # Request/response schemas
  
  routes/
    __init__.py
    users.py     # Route handlers
    
  main.py        # App setup and configuration
```

## 🎯 Next Steps

- [Pydantic Documentation](https://pydantic-docs.helpmanual.io/)
- [Nexios Error Handling](/guide/error-handling)
- [API Reference](/api-reference)
