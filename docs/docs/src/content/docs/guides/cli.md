---
title: sillo CLI Guide
description: sillo provides a powerful command-line interface (CLI) that makes it easy to develop, test, and deploy your applications. This guide will walk you through using the CLI, starting with basic
  commands and gradually introducing the configuration system.
head:
- tag: meta
  attrs:
    property: og:title
    content: sillo CLI Guide
- tag: meta
  attrs:
    property: og:description
    content: sillo provides a powerful command-line interface (CLI) that makes it easy to develop, test, and deploy your applications. This guide will walk you through using the CLI, starting with basic
      commands and gradually introducing the configuration system.
---
#  sillo CLI Guide

sillo provides a powerful command-line interface (CLI) that makes it easy to develop, test, and deploy your applications. This guide will walk you through using the CLI, starting with basic commands and gradually introducing the configuration system.

##  Installation

First, install the sillo CLI with the `cli` extra:

```bash
pip install sillo[cli]
```

##  Basic Commands

```bash
# Show help and available commands
sillo --help

# Run a simple application (defaults to main:app on port 8000)
sillo run

# Run in development mode with auto-reload
sillo dev

# List all registered routes
sillo urls

# Check if a specific route exists
sillo ping /api/status

# Start an interactive Python shell with your app loaded
sillo shell
```

##  Configuration with sillo.config.py

As your project grows, you'll want to customize how sillo runs your application. This is where `sillo.config.py` comes in.

### Creating a Basic Config

Create a `sillo.config.py` file in your project root. Here's a minimal example:

```python
# sillo.config.py
app_path = "main:app"  # Path to your FastAPI/Starlette app
port = 8000           # Default port
host = "127.0.0.1"    # Default host
```

### How Configuration Works

1. **Automatic Loading**: When you run any `sillo` command, it automatically looks for `sillo.config.py` in your current directory.
2. **Simple Variables**: Configuration is done through Python variables, making it easy to understand and modify.
3. **Type Safety**: The CLI validates your configuration when your application starts.

### Common Configuration Options

Here are the most frequently used configuration options:

- `app_path` (required): Path to your application instance in `module:app` format
- `host`: The host to bind to (default: "127.0.0.1")
- `port`: The port to run on (default: 8000)
- `reload`: Enable auto-reload in development (default: False in production, True in `sillo dev`)

### Development vs Production

#### Development Configuration

```python
# sillo.config.py
app_path = "src.main:app"
host = "127.0.0.1"
port = 5000
reload = True  # Enable auto-reload
log_level = "debug"
```

#### Production Configuration

```python
# sillo.config.py
app_path = "myapp.main:app"
host = "0.0.0.0"
port = 80
workers = 4  # For production servers that support workers
log_level = "info"
```

##  How Commands Use the Config

Each sillo command uses the configuration in different ways:

### `sillo run`
- Uses: `app_path`, `host`, `port`, `server`, `workers`, `log_level`
- Example: `sillo run --port 8080` (overrides config port)

### `sillo dev`
- Always enables `reload` and debug mode
- Uses same config as `run` but with development defaults

### `sillo urls` and `sillo ping`
- Uses: `app_path` to load your application
- Example: `sillo urls` shows all routes

##  Advanced Configuration



### Multiple Environments

Handle different environments in one config file:

```python
import os

env = os.getenv("ENV", "development")

if env == "production":
    app_path = "myapp.main:app"
    host = "0.0.0.0"
    port = 80
    log_level = "warning"
else:  # development
    app_path = "main:app"
    host = "127.0.0.1"
    port = 8000
    reload = True
    log_level = "debug"
sillo urls
sillo ping /about
```

### 2. **Production (Gunicorn)**

```python
# sillo.config.py
app_path = "src.main:app"
server = "gunicorn"
port = 80
host = "0.0.0.0"
workers = 8
log_level = "info"
```

```bash
sillo run
```

### 3. **Custom Command**

```python
# sillo.config.py
app_path = "myproject.main:app"
custom_command = "gunicorn -w 4 -b 0.0.0.0:9000 myproject.main:app"
```

```bash
sillo run
```

---

##  Advanced: app vs. app_path

- `app_path` (recommended): The string path to your app instance, e.g. `main:app`. Used by all CLI commands to dynamically import your app.
- `app` (optional): If you want to use your app instance directly in Python scripts or for advanced CLI scripting, you can define it in `sillo.config.py`. Otherwise, it is not needed.

---

##  Troubleshooting & Migration

- **Error: Could not find app module**: Make sure `app_path` is set in `sillo.config.py` and points to a valid module:variable.
- **Error: Could not load the app instance**: Check that your `app_path` is correct and the module is importable.
- **Switching from old config**: Just move your options to plain variables in `sillo.config.py` and set `app_path`.
- **Custom server logic**: Use `custom_command` for full control.

---

##  Best Practices

- Always set `app_path` in your config for maximum compatibility.
- Use `server = "gunicorn"` for production, `uvicorn` for development.
- Use `sillo dev` for local development with auto-reload and debug.
- Use `sillo shell` for interactive debugging and testing.
- Keep your config expressive and version-controlled.

---

##  Further Reading

- [sillo Routing](./routing.md)
- [sillo Middleware](./middleware.md)
- [sillo Configuration Reference](./configuration.md)
- [sillo URL Configuration](./url-configuration.md)

---

With this setup, sillo CLI is fully driven by your project config, making development, debugging, and deployment seamless and consistent.
