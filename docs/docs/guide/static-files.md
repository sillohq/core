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

# 📂 Static Files

Serving static files is a common requirement for web applications. Nexios provides a robust and flexible system for serving static assets like CSS, JavaScript, images, and other file types with security and performance in mind.

## 🚀 Basic Setup

To serve static files in Nexios, use the `StaticFiles` class:

```python
from nexios import NexiosApp
from nexios.static import StaticFiles

app = NexiosApp()

# Create a static files handler for a single directory
static_files = StaticFiles(directory="static")

# Register the static files handler with a prefix
app.register(static_files, prefix="/static")
```

With this setup, a file at `static/css/style.css` would be accessible at `/static/css/style.css`.

### Single Directory

The simplest configuration uses a single directory for all static files:

```python
static_files = StaticFiles(directory="static")
app.register(static_files, prefix="/static")
```

## 📁 Multiple Directories

For more complex setups, you can serve files from multiple directories:

```python
static_files = StaticFiles(directories=["static", "public/assets", "uploads"])
app.register(static_files, prefix="/static")
```

When serving from multiple directories, Nexios searches for files in the order the directories are specified.

## 🛣️ URL Prefixing

The `prefix` parameter defines the URL path under which static files are served:

```python
static_files = StaticFiles(directory="static")
app.register(static_files, prefix="/assets")  # Serve files at /assets/ instead of /static/
```


## 📚 Examples

### Complete Application Setup

```python
from nexios import NexiosApp
from nexios.static import StaticFiles

app = NexiosApp()

# Serve static files with optimizations
static_files = StaticFiles(
    directory="static",
    prefix="/static",
    cache_control="public, max-age=3600",
    allowed_extensions=["css", "js", "png", "jpg"]
)

app.register(static_files)

# Add middleware for logging
app.add_middleware(StaticFileLogger())
```

## 🔒 Security & Extension Filtering

For security reasons, you can restrict which file extensions are allowed to be served:

```python
# Only allow specific file extensions
static_files = StaticFiles(
    directory="static",
    allowed_extensions=["css", "js", "png", "jpg", "jpeg", "gif", "svg", "ico"]
)
app.register(static_files, prefix="/static")
```

This prevents serving potentially dangerous files like `.php`, `.py`, or other executable files.

## 🚫 Custom 404 Handler

You can provide a custom handler for when static files are not found:

```python
def custom_404_handler(request, response):
    """Custom 404 handler for static files"""
    return response.html(
        """
        <html>
            <head><title>Custom 404</title></head>
            <body>
                <h1>Custom 404 - File Not Found</h1>
                <p>The requested file could not be found.</p>
                <p><a href="/">Go back home</a></p>
            </body>
        </html>
        """,
        status_code=404
    )

static_files = StaticFiles(
    directory="static",
    custom_404_handler=custom_404_handler
)
app.register(static_files, prefix="/static")
```

## ⚡ Performance & Caching

### Cache Control

Configure caching headers for better performance:

```python
static_files = StaticFiles(
    directory="static",
    cache_control="public, max-age=3600"  # Cache for 1 hour
)
app.register(static_files, prefix="/static")
```

## 📋 Advanced Configuration

You can combine all these features for a fully configured static file server:

```python
def custom_not_found(request, response):
    """Custom 404 page with styling"""
    return response.html(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Page Not Found</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .container { max-width: 600px; margin: 0 auto; }
                h1 { color: #333; }
                a { color: #007bff; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚫 File Not Found</h1>
                <p>The requested file could not be found on this server.</p>
                <p><a href="/">Return to Home</a></p>
            </div>
        </body>
        </html>
        """,
        status_code=404
    )

# Advanced static file configuration
static_files = StaticFiles(
    directories=["static", "assets", "uploads"],
    allowed_extensions=["css", "js", "png", "jpg", "jpeg", "gif", "svg", "ico", "txt", "pdf"],
    custom_404_handler=custom_not_found,
    cache_control="public, max-age=86400",  # Cache for 24 hours
)

app.register(static_files, prefix="/static")
```
