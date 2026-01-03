---
icon: gear-code
title: Configuration Management
description: Learn how to use configuration utilities in Nexios
head:
  - - meta
    - property: og:title
      content: Configuration Management
  - - meta
    - property: og:description
      content: Learn how to use configuration utilities in Nexios
---

# ⚙️ Configuration Management
 
Nexios provides a simple way to manage configuration settings, using the `MakeConfig` class.

```python
from nexios import NexiosApp
from nexios.config import MakeConfig

config = MakeConfig(
    port=8000,
    debug=True,
    secret_key="your-secret-key-here",
)

app = NexiosApp(config=config)
```

You can access the configuration using the `config` attribute of the `NexiosApp` instance:

```python
from nexios import NexiosApp
from nexios.config import MakeConfig

config = MakeConfig({
    "port": 8000,
    "debug": True,
    "database_url": "postgresql://user:pass@localhost/dbname"
})

app = NexiosApp(config=config)

# Access configuration values
print(app.config.port)  # Output: 8000
print(app.config.debug)  # Output: True
print(app.config.database_url)  # Output: postgresql://user:pass@localhost/dbname

# Configuration is immutable by default
try:
    app.config.port = 9000  # This will raise an error
except AttributeError:
    print("Configuration is immutable")
```

## 🌍 Global Configuration Access

The framework provides global configuration management through the `get_config()` function, allowing you to access configuration from anywhere in your application:

```python
from nexios.config import get_config, set_config
from nexios import NexiosApp

# Set up configuration
config = MakeConfig({
    "port": 8000,
    "debug": True,
    "database_url": "postgresql://user:pass@localhost/dbname"
})

app = NexiosApp(config=config)

# Access global configuration from startup handler
@app.on_startup
async def startup_handler():
    config = get_config()
    print(f"Starting server on port {config.port}")
    print(f"Debug mode: {config.debug}")
    print(f"Database URL: {config.database_url}")

# Get global configuration from any handler
@app.get("/config")
async def get_config_handler(request, response):
    config = get_config()
    return response.json({
        "port": config.port,
        "debug": config.debug,
        "database_url": config.database_url
    })

# Access configuration from utility functions
def get_database_connection():
    config = get_config()
    return create_connection(config.database_url)
```

::: warning ⚠️Warning
You get access to the global configuration through the `get_config()` function from any module in your application. However, if you try to call `get_config()` before it has been set, it will raise a `RuntimeError`.
:::

::: warning Configuration in Tests
When writing tests, be aware that `get_config()` relies on a global variable. If you modify the configuration in one test without resetting it, other tests running in parallel or subsequent tests might fail unexpectedly. Always reset the configuration in your test teardown or use fixtures to ensure a clean state for each test.
:::



## 🌐 Environment-Based Configuration

### 🔧 Using Environment Variables

Environment variables are the most common way to configure applications in different environments:

```python
import os
from nexios import NexiosApp, MakeConfig

# Load configuration from environment variables
config = MakeConfig(
    debug = os.getenv("DEBUG", "False").lower() == "true",
    secret_key = os.getenv("SECRET_KEY", "default-secret-key"),
    database_url= os.getenv("DATABASE_URL", "sqlite:///app.db"),
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379"),
    port = int(os.getenv("PORT", "8000")),
    host = os.getenv("HOST", "127.0.0.1"),
    log_level = os.getenv("LOG_LEVEL", "INFO")
)

app = NexiosApp(config=config)
```

### 📄 Using .env Files

For development, you can use `.env` files to manage environment variables:

```python
from nexios import NexiosApp, MakeConfig
from nexios.config import load_env
import os

# Load environment variables from .env file
load_env()

config = MakeConfig(
    debug= os.getenv("DEBUG", "False").lower() == "true",
    secret_key= os.getenv("SECRET_KEY"),
    database_url= os.getenv("DATABASE_URL"),
    redis_url= os.getenv("REDIS_URL"),
    port= int(os.getenv("PORT", "8000")),
    host=  os.getenv("HOST", "127.0.0.1")
)

app = NexiosApp(config=config)
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



## 🏗️ Advanced Configuration Patterns

### 🔗 Nested Configuration

For complex applications, you can use nested configuration structures:

```python
from nexios import NexiosApp, MakeConfig

config = MakeConfig(**{
    "server": dict(
        host="127.0.0.1",
        port=8000,
        workers=4
    ),
    "database": dict(
        url="postgresql://user:pass@localhost/dbname",
        pool_size=20,
        max_overflow=30,
        timeout=30
    ),
    "redis": dict(
        url="redis://localhost:6379",
        pool_size=10,
        timeout=5
    ),
    "security": dict(
        secret_key="your-secret-key",
        session_timeout=3600,
        csrf_enabled=True
    ),
    "logging": dict(
        level="INFO",
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        file="app.log"
    )
})

app = NexiosApp(config=config)

# Access nested configuration
print(app.config.server.host)  # 127.0.0.1
print(app.config.database.pool_size)  # 20
print(app.config.security.csrf_enabled)  # True
```


This comprehensive configuration guide covers all aspects of managing configuration in Nexios applications. The configuration system is designed to be flexible, secure, and easy to use while providing the power to handle complex configuration scenarios across different environments.

