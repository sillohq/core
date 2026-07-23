---
title: sillo CLI Guide
description: Run, inspect, and debug Sillo applications from the command line.
---

# sillo CLI Guide

The Sillo CLI runs and inspects your application directly from command arguments. It does not use a project configuration file.

## Installation

Install the CLI extra with `uv`:

```bash
uv add "sillo[cli]"
```

## Basic Commands

```bash
# Show help and available commands
sillo --help

# Run main:app on the default port
sillo run main:app

# Run with auto-reload during development
sillo dev main:app

# List registered routes
sillo urls main:app

# Check if a route exists
sillo ping main:app /api/status

# Start an interactive shell with the app loaded
sillo shell main:app
```

## Run an App

Pass your app as `module:variable`:

```bash
sillo run main:app --host 127.0.0.1 --port 8000
```

For development:

```bash
sillo dev main:app --port 5000
```

## Inspect Routes

Use `urls` to print every registered route:

```bash
sillo urls main:app
```

Use `ping` to verify one route:

```bash
sillo ping main:app /users
```

## Shell

Open an interactive shell with your application imported:

```bash
sillo shell main:app
```

## Best Practices

- Keep the app entrypoint explicit: `main:app`, `src.main:app`, or similar.
- Use `sillo dev` locally for auto-reload.
- Use `sillo run` for direct local serving.
- Use your deployment platform or process manager for production options.

## Further Reading

- [Routing](./routing.md)
- [Middleware](./middleware.md)
- [Installation](./installation.md)
