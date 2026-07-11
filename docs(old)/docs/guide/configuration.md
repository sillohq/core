---
icon: gear-code
title: Configuration Management
description: Learn how to use configuration utilities in sillo
head:
  - - meta
    - property: og:title
      content: Configuration Management
  - - meta
    - property: og:description
      content: Learn how to use configuration utilities in sillo
---

# Configuration Management

sillo applications are configured by passing settings directly to the app or middleware:

```python
from sillo import silloApp

app = silloApp()

# Configure the app
app.config.port = 8000
app.config.debug = True
```

You can also set configuration values directly:

```python
from sillo import silloApp

app = silloApp()
app.config.database_url = "postgresql://user:pass@localhost/dbname"

# Access configuration values
print(app.config.port)          # Output: 8000 (default)
print(app.config.debug)          # Output: False (default)
print(app.config.database_url)    # Output: postgresql://user:pass@localhost/dbname
```

For middleware-specific config, pass settings directly:

```python
from sillo import silloApp
from sillo.middleware.cors import CorsConfig, CORSMiddleware

app = silloApp()
app.add_middleware(
    CORSMiddleware(
        config=CorsConfig(
            allow_origins=["https://example.com"],
            allow_methods=["GET", "POST"]
        )
    )
)
```

Configuration is immutable by default:

```python
# Configuration is immutable by default
try:
    app.config.port = 9000  # This will raise an error
except AttributeError:
    print("Configuration is immutable")
```

## Global Configuration Access

The framework provides global configuration management through `app.config`, allowing you to access configuration from anywhere in your application:

```python
from sillo import silloApp

app = silloApp()
app.config.port = 8000
app.config.debug = True
app.config.database_url = "postgresql://user:pass@localhost/dbname"

# Access configuration from startup handler
@app.on_startup
async def startup_handler():
    print(f"Starting server on port {app.config.port}")
    print(f"Debug mode: {app.config.debug}")
    print(f"Database URL: {app.config.database_url}")

# Get configuration from any handler
@app.get("/config")
async def get_config_handler(request, response):
    return response.json({
        "port": app.config.port,
        "debug": app.config.debug,
        "database_url": app.config.database_url
    })

# Access configuration from utility functions
def get_database_connection():
    return create_connection(app.config.database_url)
```

::: warning ⚠️Warning
You can access the configuration through `app.config` from any module in your application. However, if you modify the configuration in one test without resetting it, other tests running in parallel or subsequent tests might fail unexpectedly. Always reset the configuration in your test teardown or use fixtures to ensure a clean state for each test.
:::

## Environment-Based Configuration

### Using Environment Variables

Environment variables are the most common way to configure applications in different environments:

```python
import os
from sillo import silloApp

app = silloApp()
app.config.debug = os.getenv("DEBUG", "False").lower() == "true"
app.config.secret_key = os.getenv("SECRET_KEY", "default-secret-key")
app.config.database_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
app.config.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
app.config.port = int(os.getenv("PORT", "8000"))
app.config.host = os.getenv("HOST", "127.0.0.1")
app.config.log_level = os.getenv("LOG_LEVEL", "INFO")
```

### Using .env Files

For development, you can use `.env` files to manage environment variables:

```python
from sillo import silloApp
from sillo.config import load_env
import os

# Load environment variables from .env file
load_env()

app = silloApp()
app.config.debug = os.getenv("DEBUG", "False").lower() == "true"
app.config.secret_key = os.getenv("SECRET_KEY")
app.config.database_url = os.getenv("DATABASE_URL")
app.config.redis_url = os.getenv("REDIS_URL")
app.config.port = int(os.getenv("PORT", "8000"))
app.config.host = os.getenv("HOST", "127.0.0.1")
```

Example `.env` file:

```ini
# Development Environment
DEBUG=true
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=postgresql://user:pass@localhost/dev_db
REDIS_URL=redis://localhost:6379
PORT=8000
HOST=127.0.0.1
LOG_LEVEL=DEBUG
```

## Advanced Configuration Patterns

### Nested Configuration

For complex applications, you can use nested configuration structures directly on `app.config`:

```python
from sillo import silloApp

app = silloApp()

# Server config
app.config.server_host = "127.0.0.1"
app.config.server_port = 8000
app.config.server_workers = 4

# Database config
app.config.database_url = "postgresql://user:pass@localhost/dbname"
app.config.database_pool_size = 20
app.config.database_max_overflow = 30
app.config.database_timeout = 30

# Redis config
app.config.redis_url = "redis://localhost:6379"
app.config.redis_pool_size = 10
app.config.redis_timeout = 5

# Security config
app.config.secret_key = "your-secret-key"
app.config.session_timeout = 3600
app.config.csrf_enabled = True

# Logging config
app.config.logging_level = "INFO"
app.config.logging_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
app.config.logging_file = "app.log"

# Access nested configuration
print(app.config.server_host)      # 127.0.0.1
print(app.config.database_pool_size)   # 20
print(app.config.csrf_enabled)        # True
```

This comprehensive configuration guide covers all aspects of managing configuration in sillo applications. The configuration system is designed to be flexible, secure, and easy to use while providing the power to handle complex configuration scenarios across different environments.
