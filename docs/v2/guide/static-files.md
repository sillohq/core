---
title: Static Files
description: Serving static files is a common requirement for web applications. Nexios provides a robust and flexible system for serving static assets like CSS, JavaScript, images, and other file types with security and performance in mind.
head:
  - - meta
    - property: og:title
      content: Static Files
  - - meta
    - property: og:description
      content: Serving static files is a common requirement for web applications. Nexios provides a robust and flexible system for serving static assets like CSS, JavaScript, images, and other file types with security and performance in mind.
---

# Static Files

Serving static files is a common requirement for web applications. Nexios provides a robust and flexible system for serving static assets like CSS, JavaScript, images, and other file types with security and performance in mind.

::: warning ⚠️ Deprecated
The `StaticFilesHandler` class is deprecated and will be removed in a future version. Please use the new `StaticFiles` class instead.
:::

## Basic Setup

To serve static files in Nexios, you can use either the new `StaticFiles` class or the deprecated `StaticFilesHandler`:

### Using StaticFiles (Recommended)

```python
from nexios import NexiosApp
from nexios.static import StaticFiles

app = NexiosApp()

# Create a static files handler for a single directory
static_files = StaticFiles(directory="static")

# Register the static files handler with a prefix
app.register(static_files, prefix="/static")
```

### Using StaticFilesHandler (Deprecated)

```python
from nexios import NexiosApp
from nexios.static import StaticFilesHandler
from nexios.routing import Route

app = NexiosApp()

# Create a static files handler for a single directory
static_handler = StaticFilesHandler(
    directory="static",  # Directory relative to the application root
    url_prefix="/static/"  # URL prefix for accessing static files
)

# Add a route for static files
app.add_route(
    Route(
        "/static/{path:path}",
        static_handler
    )
)
```

With this setup, a file at `static/css/style.css` would be accessible at `/static/css/style.css`.

### Single Directory

The simplest configuration uses a single directory for all static files:

```python
# Using StaticFiles (Recommended)
static_files = StaticFiles(directory="static")
app.register(static_files, prefix="/static")

# Using StaticFilesHandler (Deprecated)
static_handler = StaticFilesHandler(
    directory="static",
    url_prefix="/static/"
)
```

## Multiple Directories

For more complex setups, you can serve files from multiple directories:

```python
# Using StaticFiles (Recommended)
static_files = StaticFiles(directories=["static", "public/assets", "uploads"])
app.register(static_files, prefix="/static")

# Using StaticFilesHandler (Deprecated)
static_handler = StaticFilesHandler(
    directories=["static", "public/assets", "uploads"],
    url_prefix="/static/"
)
```

When serving from multiple directories, Nexios searches for files in the order the directories are specified.

## URL Prefixing

The `prefix` parameter (for `StaticFiles`) or `url_prefix` parameter (for `StaticFilesHandler`) defines the URL path under which static files are served:

```python
# Using StaticFiles (Recommended)
static_files = StaticFiles(directory="static")
app.register(static_files, prefix="/assets")  # Serve files at /assets/ instead of /static/

# Using StaticFilesHandler (Deprecated)
static_handler = StaticFilesHandler(
    directory="static",
    url_prefix="/assets/"  # Serve files at /assets/ instead of /static/
)
```

