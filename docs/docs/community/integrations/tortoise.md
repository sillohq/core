# Tortoise ORM Integration

The `nexios_contrib.tortoise` package provides seamless integration between Nexios and [Tortoise ORM](https://tortoise.github.io/), an easy-to-use asyncio ORM inspired by Django ORM.

## Features

- 🚀 **Easy Setup**: Simple initialization with minimal configuration
- 🔄 **Lifecycle Management**: Automatic startup and shutdown handling
- 🛡️ **Exception Handling**: Built-in handlers for common database exceptions
- 🏗️ **Schema Management**: Optional automatic schema generation
- 🔗 **Multiple Databases**: Support for multiple database connections
- 📝 **Type Safety**: Full type hints and IDE support

## Installation

Install the Tortoise ORM integration:

```bash
pip install nexios_contrib[tortoise]
# or
pip install tortoise-orm
```

## Quick Start

### Basic Setup

```python
from nexios import NexiosApp
from nexios_contrib.tortoise import init_tortoise

app = NexiosApp()

# Initialize Tortoise ORM
init_tortoise(
    app,
    db_url="sqlite://db.sqlite3",
    modules={"models": ["app.models"]},
    generate_schemas=True
)
```

### Define Models

```python
# app/models.py
from tortoise.models import Model
from tortoise import fields

class User(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    email = fields.CharField(max_length=255, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "users"

class Post(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=200)
    content = fields.TextField()
    author = fields.ForeignKeyField("models.User", related_name="posts")
    created_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "posts"
```

### Use in Route Handlers

```python
@app.get("/users")
async def list_users(request, response):
    users = await User.all()
    return response.json([
        {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
        for user in users
    ])

@app.get("/users/{user_id}")
async def get_user(request, response):
    user_id = request.path_params["user_id"]
    try:
        user = await User.get(id=user_id)
        return response.json({
            "id": user.id,
            "name": user.name,
            "email": user.email
        })
    except User.DoesNotExist:
        # Automatically handled by exception handlers
        # Returns 404 with proper error message
        raise

@app.post("/users")
async def create_user(request, response):
    data = await request.json()
    try:
        user = await User.create(
            name=data["name"],
            email=data["email"]
        )
        return response.status(201).json({
            "id": user.id,
            "name": user.name,
            "email": user.email
        })
    except Exception:
        # IntegrityError (duplicate email) automatically handled
        # Returns 400 with proper error message
        raise
```

## Configuration

### Environment Variables

```python
from nexios_contrib.tortoise import TortoiseConfig

# Load from environment variables
config = TortoiseConfig.from_env()
init_tortoise(app, **config.dict())
```

Set these environment variables:
```bash
TORTOISE_DB_URL=postgresql://user:password@localhost:5432/mydb
TORTOISE_GENERATE_SCHEMAS=true
TORTOISE_USE_TZ=true
TORTOISE_MODULES='{"models": ["app.models", "app.user_models"]}'
```

### Multiple Databases

```python
init_tortoise(
    app,
    db_url="sqlite://main.db",
    modules={
        "models": ["app.models"],
        "users": ["app.user_models"],
        "analytics": ["app.analytics_models"]
    },
    connections={
        "default": "sqlite://main.db",
        "users_db": "postgresql://user:pass@localhost/users",
        "analytics_db": "postgresql://user:pass@localhost/analytics"
    }
)
```

## Exception Handling

The integration automatically handles common Tortoise ORM exceptions:

### Built-in Exception Handlers

- **IntegrityError** → 400 Bad Request
- **DoesNotExist** → 404 Not Found  
- **ValidationError** → 422 Unprocessable Entity
- **ConnectionError** → 503 Service Unavailable
- **TransactionError** → 500 Internal Server Error



### Disable Exception Handlers

```python
init_tortoise(
    app,
    db_url="sqlite://db.sqlite3",
    modules={"models": ["app.models"]},
    add_exception_handlers=False  # Disable automatic exception handling
)
```


### Using Transactions
```python
from tortoise.transactions import in_transaction

@app.post("/transfer")
async def transfer_funds(request, response):
    data = await request.json()
    
    async with in_transaction():
        # All operations in this block are transactional
        sender = await User.get(id=data["sender_id"])
        receiver = await User.get(id=data["receiver_id"])
        
        sender.balance -= data["amount"]
        receiver.balance += data["amount"]
        
        await sender.save()
        await receiver.save()
        
        return response.json({"status": "success"})
```

## Supported Databases

- **SQLite**: `sqlite://path/to/db.sqlite3`
- **PostgreSQL**: `postgres://user:password@host:port/database`
- **MySQL**: `mysql://user:password@host:port/database`
- **AsyncPG**: `asyncpg://user:password@host:port/database`
- **AioMySQL**: `aiomysql://user:password@host:port/database`

## Best Practices

1. **Always use transactions** for operations that modify multiple records
2. **Handle exceptions gracefully** with proper HTTP status codes
3. **Use connection pooling** for production deployments
4. **Validate input data** before database operations
5. **Use indexes** on frequently queried fields
6. **Monitor database performance** in production

## Migration from FastAPI

If you're migrating from FastAPI's Tortoise integration:

```python
# FastAPI style
from fastapi import FastAPI
from tortoise.contrib.fastapi import register_tortoise

app = FastAPI()
register_tortoise(
    app,
    db_url="sqlite://db.sqlite3",
    modules={"models": ["app.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

# Nexios style  
from nexios import NexiosApp
from nexios_contrib.tortoise import init_tortoise

app = NexiosApp()
init_tortoise(
    app,
    db_url="sqlite://db.sqlite3",
    modules={"models": ["app.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)
```

The API is intentionally similar to make migration easier!

## API Reference

### `init_tortoise(app, db_url, modules=None, generate_schemas=False, add_exception_handlers=True, **kwargs)`

Initialize Tortoise ORM for a Nexios application.

**Parameters:**
- `app`: The Nexios application instance
- `db_url`: Database connection URL
- `modules`: Dictionary mapping app names to model module paths
- `generate_schemas`: Whether to generate database schemas on startup
- `add_exception_handlers`: Whether to add Tortoise exception handlers
- `**kwargs`: Additional arguments to pass to Tortoise.init()

### `get_tortoise_client()`

Get the Tortoise ORM client instance for raw SQL operations.

**Returns:** TortoiseClient instance

**Raises:** TortoiseConnectionError if not initialized

### `TortoiseConfig`

Configuration class for Tortoise ORM settings.

**Methods:**
- `from_env(prefix="TORTOISE_")`: Create config from environment variables
- `to_tortoise_config()`: Convert to Tortoise.init() kwargs



## Contributing

Contributions are welcome! Please see the [contribution guide](../contribution-guide.md) for details.