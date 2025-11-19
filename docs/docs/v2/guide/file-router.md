---
title: Nexios File Router Guide
description: Nexios provides a powerful file router system that makes it easy to develop, test, and deploy your applications. This guide will walk you through using the file router system, starting with basic commands and gradually introducing the configuration system.
head:
  - - meta
    - property: og:title
      content: Nexios File Router Guide
  - - meta
    - property: og:description
      content: Nexios provides a powerful file router system that makes it easy to develop, test, and deploy your applications. This guide will walk you through using the file router system, starting with basic commands and gradually introducing the configuration system.
---

Here's a comprehensive rewrite with clear subheadings and improved explanations, including the dynamic parameter notation change:

---

# Nexios File Router System: Complete Guide

## Introduction to File-Based Routing

### What is File Routing?
File routing is an intuitive system where your application's URL structure mirrors your project's file structure. Instead of manually defining routes in code, the framework automatically creates routes based on files named `route.py` in your directory tree.

### Key Benefits of File Routing
- **Visual API Structure**: Your folder hierarchy directly represents your API endpoints
- **Reduced Boilerplate**: Eliminates repetitive route registration code
- **Improved Maintainability**: Related endpoints stay grouped logically
- **Faster Development**: New endpoints are created by adding files
- **Consistent Conventions**: Standardized approach across projects

## Core Configuration

### Basic Setup Example
```python
from nexios import NexiosApp
from nexios.file_router import FileRouter

app = NexiosApp()

# Initialize File Router with default settings
FileRouter(app, config={
    "root": "./routes",
    "exempt_paths": [],
    "exclude_from_schema": False
})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Configuration Options Explained

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `root` | str | Base directory for route files | `"./routes"` |
| `exempt_paths` | List[str] | Path patterns to exclude from routing | `[]` |
| `exclude_from_schema` | bool | Hide these routes from OpenAPI docs | `False` |

## Directory Structure Conventions

### Basic Route File Structure
```
routes/
├── route.py              # → /
├── users/
│   ├── route.py          # → /users
│   └── {user_id}/        # Dynamic segment
│       └── route.py      # → /users/{user_id}
└── products/
    ├── route.py          # → /products
    └── {category}/       # Dynamic segment
        └── route.py      # → /products/{category}
```

### Important Naming Rules
1. Route files must be named exactly `route.py`
2. Dynamic segments use curly braces: `{param_name}`
3. Subdirectories create nested routes

## Handling HTTP Methods

### Basic Route Handler Example
```python
# routes/users/route.py

def get(req, res):
    """GET /users - List all users"""
    return res.json(get_all_users())

def post(req, res):
    """POST /users - Create new user"""
    user_data = await req.json
    return res.json(create_user(user_data), status_code=201)
```

### Supported HTTP Methods
Simply define functions named after the HTTP verb you want to handle:
- `get()`
- `post()`
- `put()`
- `patch()`
- `delete()`
- `head()`
- `options()`

## Working with Dynamic Parameters

### Single Parameter Route
```
routes/
└── users/
    └── {user_id}/        # Creates /users/{user_id}
        └── route.py
```

Access the parameter in your handler:
```python
# routes/users/{user_id}/route.py

def get(req, res):
    user_id = req.path_params.user_id
    return res.json(get_user_by_id(user_id))
```

### Multiple/Nested Parameters
```
routes/
└── organizations/
    └── {org_id}/
        └── members/
            └── {member_id}/
                └── route.py  # → /organizations/{org_id}/members/{member_id}
```

```python
def get(req, res):
    org_id = req.path_params.org_id
    member_id = req.path_params.member_id
    return res.json(get_org_member(org_id, member_id))
```

### Catch-All Parameters
For paths that should match multiple segments:
```
routes/
└── files/
    └── {filepath:path}/  # Will match /files/any/path/here
        └── route.py
```

```python
def get(req, res):
    full_path = req.path_params.filepath
    return res.text(f"Requested file: {full_path}")
```

## Advanced Route Configuration

### Using the @mark_as_route Decorator
For complex route requirements:
```python
from nexios.file_router.utils import mark_as_route
from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    email: str

@mark_as_route(
    methods=["POST"],
    summary="Create User",
    response_model=UserCreate,
    tags=["Users"],
    status_code=201
)
async def create_user(req, res):
    data = await req.json
    return res.json(create_new_user(data))
```

### Decorator Options Reference

| Parameter | Description |
|-----------|-------------|
| `path` | Override auto-generated path |
| `methods` | Specify allowed HTTP methods |
| `summary` | OpenAPI summary |
| `description` | Detailed endpoint docs |
| `response_model` | Pydantic model for responses |
| `tags` | OpenAPI grouping tags |
| `status_code` | Default success status code |
| `deprecated` | Mark as deprecated |
| `security` | Authentication requirements |

## Template Rendering System

### HTML Template Configuration
```python
from nexios.file_router.html import configure_templates

# Basic setup
configure_templates(
    template_dir="./templates",
    auto_reload=True  # Disable in production
)
```

### Rendering Templates in Route
```python
from nexios.file_router.html import render

@render("user_profile.html")
def get(req, res):
    return {
        "user": get_user(req.path_params.user_id),
        "stats": get_user_stats()
    }
```

### Recommended Template Structure
```
templates/
├── base.html
├── users/
│   ├── profile.html
│   └── list.html
└── products/
    ├── view.html
    └── list.html
```

## Error Handling

### Custom Error Handlers
```python
@app.add_exception_handler(404)
async def not_found_handler(req, res, exc):
    return res.render("errors/404.html", status_code=404)

@app.add_exception_handler(500)
async def server_error_handler(req, res, exc):
    return res.render("errors/500.html", status_code=500)
```

## Best Practices

### Project Structure Recommendations
```
project/
├── app.py
├── routes/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── users/
│   │   │   │   ├── {id}/
│   │   │   │   │   └── route.py
│   │   │   │   └── route.py
│   │   │   └── products/
│   │   │       └── route.py
│   │   └── v2/
│   │       └── ... 
│   └── web/
│       ├── auth/
│       │   └── route.py
│       └── dashboard/
│           └── route.py
└── templates/
    ├── api/
    └── web/
```

### Performance Tips
1. Disable `auto_reload` in production
2. Use a CDN for static assets
3. Implement caching for frequently accessed routes
4. Keep template inheritance shallow

## Limitations and Workarounds

### Current Limitations
1. Requires exact `route.py` filename
2. Complex route patterns may need manual registration
3. Directory scanning occurs at startup

### Common Solutions
- For complex cases, use traditional route registration
- Implement custom middleware for special cases
- Use symlinks for alternate route organizations

---

This guide provides a comprehensive overview of Nexios's file routing system with clear hierarchical organization and practical examples. The dynamic parameter notation has been updated to use `{param_name}` consistently throughout.