---
title: Nexios CLI Guide
description: Nexios provides a powerful command-line interface (CLI) that makes it easy to develop, test, and deploy your applications. This guide will walk you through using the CLI, starting with basic commands and gradually introducing the configuration system.
head:
  - - meta
    - property: og:title
      content: Nexios CLI Guide
  - - meta
    - property: og:description
      content: Nexios provides a powerful command-line interface (CLI) that makes it easy to develop, test, and deploy your applications. This guide will walk you through using the CLI, starting with basic commands and gradually introducing the configuration system.
---
# 🛠️ Nexios CLI Guide

Nexios provides a powerful command-line interface (CLI) that makes it easy to develop, test, and deploy your applications. This guide will walk you through using the CLI, starting with basic commands and gradually introducing the configuration system.

## 📦 Installation

First, install the Nexios CLI with the `cli` extra:

```bash
pip install nexios[cli]
```

## 🎯 Basic Commands

```bash
# Show help and available commands
nexios --help

# Run a simple application (defaults to main:app on port 8000)
nexios run

# Run in development mode with auto-reload
nexios dev

# List all registered routes
nexios urls

# Check if a specific route exists
nexios ping /api/status

# Start an interactive Python shell with your app loaded
nexios shell
```

## ⚙️ Configuration with nexios.config.py

As your project grows, you'll want to customize how Nexios runs your application. This is where `nexios.config.py` comes in.

### Creating a Basic Config

Create a `nexios.config.py` file in your project root. Here's a minimal example:

```python
# nexios.config.py
app_path = "main:app"  # Path to your FastAPI/Starlette app
port = 8000           # Default port
host = "127.0.0.1"    # Default host
```

### How Configuration Works

1. **Automatic Loading**: When you run any `nexios` command, it automatically looks for `nexios.config.py` in your current directory.
2. **Simple Variables**: Configuration is done through Python variables, making it easy to understand and modify.
3. **Type Safety**: The CLI validates your configuration when your application starts.

### Common Configuration Options

Here are the most frequently used configuration options:

- `app_path` (required): Path to your application instance in `module:app` format
- `host`: The host to bind to (default: "127.0.0.1")
- `port`: The port to run on (default: 8000)
- `reload`: Enable auto-reload in development (default: False in production, True in `nexios dev`)

### Development vs Production

#### Development Configuration

```python
# nexios.config.py
app_path = "src.main:app"
host = "127.0.0.1"
port = 5000
reload = True  # Enable auto-reload
log_level = "debug"
```

#### Production Configuration

```python
# nexios.config.py
app_path = "myapp.main:app"
host = "0.0.0.0"
port = 80
workers = 4  # For production servers that support workers
log_level = "info"
```

## 🔧 How Commands Use the Config

Each Nexios command uses the configuration in different ways:

### `nexios run`
- Uses: `app_path`, `host`, `port`, `server`, `workers`, `log_level`
- Example: `nexios run --port 8080` (overrides config port)

### `nexios dev`
- Always enables `reload` and debug mode
- Uses same config as `run` but with development defaults

### `nexios urls` and `nexios ping`
- Uses: `app_path` to load your application
- Example: `nexios urls` shows all routes

## 🏭 Advanced Configuration

### Custom Server Command

For complete control, you can specify a custom command:

```python
# nexios.config.py
custom_command = "gunicorn -w 4 -k uvicorn.workers.UvicornWorker myapp.main:app"
```

### Environment Variables

You can use environment variables in your config:

```python
import os

app_path = os.getenv("APP_PATH", "main:app")
port = int(os.getenv("PORT", "8000"))
```

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
nexios urls
nexios ping /about
```

### 2. **Production (Gunicorn)**

```python
# nexios.config.py
app_path = "src.main:app"
server = "gunicorn"
port = 80
host = "0.0.0.0"
workers = 8
log_level = "info"
```

```bash
nexios run
```

### 3. **Custom Command**

```python
# nexios.config.py
app_path = "myproject.main:app"
custom_command = "gunicorn -w 4 -b 0.0.0.0:9000 myproject.main:app"
```

```bash
nexios run
```

---

## ⚡ Advanced: app vs. app_path

- `app_path` (recommended): The string path to your app instance, e.g. `main:app`. Used by all CLI commands to dynamically import your app.
- `app` (optional): If you want to use your app instance directly in Python scripts or for advanced CLI scripting, you can define it in `nexios.config.py`. Otherwise, it is not needed.

---

## 🛠️ Troubleshooting & Migration

- **Error: Could not find app module**: Make sure `app_path` is set in `nexios.config.py` and points to a valid module:variable.
- **Error: Could not load the app instance**: Check that your `app_path` is correct and the module is importable.
- **Switching from old config**: Just move your options to plain variables in `nexios.config.py` and set `app_path`.
- **Custom server logic**: Use `custom_command` for full control.

---

## 📋 Best Practices

- Always set `app_path` in your config for maximum compatibility.
- Use `server = "gunicorn"` for production, `uvicorn` for development.
- Use `nexios dev` for local development with auto-reload and debug.
- Use `nexios shell` for interactive debugging and testing.
- Keep your config expressive and version-controlled.

---

## 📚 Further Reading

- [Nexios Routing](./routing.md)
- [Nexios Middleware](./middleware.md)
- [Nexios Configuration Reference](./configuration.md)
- [Nexios URL Configuration](./url-configuration.md)

---

With this setup, Nexios CLI is fully driven by your project config, making development, debugging, and deployment seamless and consistent.
