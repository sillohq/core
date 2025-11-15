---
title: Templating
icon: template
description: >
    Nexios provides a powerful templating system built on top of Jinja2, offering features like template inheritance, context management, custom filters, and more.
head:
  - - meta
    - property: og:title
      content: Templating
    - property: og:description
      content: Nexios provides a powerful templating system built on top of Jinja2, offering features like template inheritance, context management, custom filters, and more.
---
# 🎨 Templating

Nexios provides a powerful templating system built on top of Jinja2, offering features like template inheritance, context management, custom filters, and more.

## 📋 Prerequisites

Before using templating features, you need to install the required dependencies:

```bash
pip install nexios[templating]
```

## 🚀 Quick Start

```python
from nexios import NexiosApp
from nexios.templating import render,TemplateEngine

app = NexiosApp()
engine = TemplateEngine()
engine.setup_environment()

@app.get("/")
async def home(request, response):
    return await render("home.html", {"title": "Welcome"}, request=request)
```

::: tip Tip
Without setting up the templating engine , the render function throws a Notimpemented error

:::

## ⚙️ Customizing Default Configuration

There are several ways to customize the templating system:

### 1. Using setup_environment

The simplest way is to set template options in your app configuration:

```py
from nexios.templating import  TemplateConfig

template_config = TemplateConfig(
    template_dir = "templates"
)

engine.setup_environment(template_config)
```

### 2. Using App Config

You can also nexios app config optionally

```python
from nexios import NexiosApp,MakeConfig
from nexios.templating import  TemplateConfig

config = MakeConfig(
    {
        "templating" : TemplateConfig(
            template_dir = "templates"
        )
    }
)


app = NexiosApp(config = config)
```

### 3. Runtime Configuration Updates

You can update configuration at runtime:

```python
from nexios.templating import TemplateEngine
from pathlib import Path

engine = TemplateEngine()
engine.setup_environment()


engine.env.filters["custom"] = my_custom_filter

# Add new globals
engine.env.globals.update({
    "api_version": "2.0",
    "debug": True
})

engine.config.template_dir = Path("new_templates")
engine._setup_environment()
```

## 📊 Configuration Options

The `TemplateConfig` class supports the following options:

| Option         | Type                | Default     | Description                     |
| -------------- | ------------------- | ----------- | ------------------------------- |
| template_dir   | str/Path            | "templates" | Template directory path         |
| cache_size     | int                 | 100         | Maximum templates to cache      |
| auto_reload    | bool                | True        | Reload changed templates        |
| encoding       | str                 | "utf-8"     | Template file encoding          |
| enable_async   | bool                | True        | Enable async rendering          |
| trim_blocks    | bool                | True        | Strip first newline after block |
| lstrip_blocks  | bool                | True        | Strip leading spaces and tabs   |
| custom_filters | Dict[str, callable] | {}          | Custom template filters         |
| custom_globals | Dict[str, Any]      | {}          | Global template variables       |

## 🏗️ Template Inheritance

Base template (`base.html`):

```html
<!DOCTYPE html>
<html>
  <head>
    <title>{% block title %}{% endblock %}</title>
  </head>
  <body>
    <nav>{% block nav %}{% endblock %}</nav>
    <main>{% block content %}{% endblock %}</main>
    <footer>{% block footer %}{% endblock %}</footer>
  </body>
</html>
```

Child template:

```html
{% extends "base.html" %} {% block title %}Welcome{% endblock %} {% block
content %}
<h1>{{ title }}</h1>
{{ content }} {% endblock %}
```

## 🔧 Context Middleware

Add global and request-specific context to your templates:

```python
from nexios.templating.middleware import template_context

async def user_context(request):
    return {
        "user": await get_current_user(request),
        "messages": await get_flash_messages(request)
    }

app.add_middleware(template_context(
    default_context={
        "version": "1.0.0",
        "nav_links": [...]
    },
    context_processor=user_context
))
```

## Utility Functions

The templating system includes several utility functions:

```python
from nexios.templating.utils import (
    truncate,
    format_datetime,
    static_hash,
    merge_dicts
)

# Truncate text
{{ long_text|truncate(100) }}

# Format dates
{{ date|format_datetime("%Y-%m-%d") }}

# Cache busting for static files
{{ static_url('style.css') }}?v={{ static_hash('static/style.css') }}
```

## ✅ Best Practices

1. **Template Organization**

   - Keep templates in a dedicated directory
   - Use meaningful names and subdirectories
   - Follow a consistent naming convention

2. **Context Management**

   - Use middleware for global context
   - Keep context processors focused and lightweight
   - Cache expensive context operations

3. **Performance**

   - Enable template caching in production
   - Use async rendering for I/O operations
   - Minimize template complexity

4. **Security**
   - HTML escaping is enabled by default
   - Use `|safe` filter carefully
   - Validate user input before rendering

## 📚 API Reference

### Render Function

```python
async def render(
    template_name: str,
    context: Dict[str, Any] = None,
    status_code: int = 200,
    headers: Dict[str, str] = None,
    request: Request = None,
    **kwargs
) -> Response
```

### Template Context Middleware

```python
def template_context(
    default_context: Optional[Dict[str, Any]] = None,
    context_processor: Optional[
        Callable[[Request], Awaitable[Dict[str, Any]]]
    ] = None
) -> TemplateContextMiddleware
```

### Utility Functions

```python
def truncate(text: str, length: int = 100, suffix: str = "...") -> str
def format_datetime(value: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str
def static_hash(filepath: str) -> str
def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]
```

## ⚡ Advanced Templating

This guide covers advanced features and patterns for the Nexios templating system.

## 🎯 Custom Filters

Create and register custom template filters:

```python
from nexios.templating import TemplateConfig

def markdown_to_html(text: str) -> str:
    import markdown
    return markdown.markdown(text)

def currency(value: float, symbol: str = "$") -> str:
    return f"{symbol}{value:,.2f}"

config = TemplateConfig(
    custom_filters={
        "markdown": markdown_to_html,
        "currency": currency
    }
)
```

Usage in templates:

```html
{{ post.content|markdown }} {{ product.price|currency("€") }}
```

## 🔧 Macros

Create reusable template components:

```html
{# macros/forms.html #} {% macro input(name, value='', type='text', label='') %}
<div class="form-group">
  {% if label %}
  <label for="{{ name }}">{{ label }}</label>
  {% endif %}
  <input
    type="{{ type }}"
    name="{{ name }}"
    value="{{ value }}"
    id="{{ name }}"
  />
</div>
{% endmacro %} {# Usage in templates #} {% from "macros/forms.html" import input
%}
<form method="post">
  {{ input('username', label='Username') }} {{ input('password',
  type='password', label='Password') }}
</form>
```

## 🔄 Async Template Functions

Create async template functions for database queries or API calls:

```python
from nexios.templating import TemplateConfig
from functools import partial

async def get_user_posts(user_id: int):
    # Async database query
    return await db.query("SELECT * FROM posts WHERE user_id = $1", user_id)

config = TemplateConfig(
    custom_globals={
        "get_posts": get_user_posts
    }
)
```

Usage in templates:

```html
{% set posts = await get_posts(user.id) %} {% for post in posts %}
<article>{{ post.title }}</article>
{% endfor %}
```

## 📦 Context Processors

Advanced context processor patterns:

```python
from typing import Dict, Any
from nexios.templating.middleware import template_context
from nexios.cache import cached

class ContextBuilder:
    def __init__(self):
        self.processors = []

    def add(self, processor):
        self.processors.append(processor)
        return self

    async def build(self, request) -> Dict[str, Any]:
        context = {}
        for proc in self.processors:
            context.update(await proc(request))
        return context

@cached(ttl=300)  # Cache for 5 minutes
async def get_site_stats(request):
    return {
        "total_users": await db.count("users"),
        "total_posts": await db.count("posts")
    }

async def get_user_data(request):
    if user := await get_current_user(request):
        return {
            "user": user,
            "notifications": await get_user_notifications(user.id)
        }
    return {}

# Combine processors
context_builder = (
    ContextBuilder()
    .add(get_site_stats)
    .add(get_user_data)
)

app.add_middleware(template_context(
    context_processor=context_builder.build
))
```

## 💾 Template Caching

Implement template fragment caching:

```python
from nexios.cache import Cache
from nexios.templating import TemplateConfig

cache = Cache()

async def cached_fragment(key: str, ttl: int = 300):
    """Template fragment cache."""
    if content := await cache.get(key):
        return content
    return None

config = TemplateConfig(
    custom_globals={
        "cached_fragment": cached_fragment,
        "cache": cache
    }
)
```

Usage in templates:

```html
{% set cache_key = 'sidebar_' + user.id %} {% set cached = await
cached_fragment(cache_key) %} {% if cached %} {{ cached }} {% else %} {% set
content %} {# Expensive sidebar rendering #}
<aside>...</aside>
{% endset %} {{ cache.set(cache_key, content, ttl=300) }} {{ content }} {% endif
%}
```

## ⚠️ Error Handling

Custom error templates and handling:

```python
from nexios.templating import render
from nexios.exceptions import TemplateError

@app.exception_handler(404)
async def not_found(request, exc):
    return await render(
        "errors/404.html",
        {"path": request.url.path},
        status_code=404
    )

@app.exception_handler(TemplateError)
async def template_error(request, exc):
    return await render(
        "errors/template.html",
        {
            "error": str(exc),
            "template": exc.template_name,
            "lineno": exc.lineno
        },
        status_code=500
    )
```

## 🧪 Testing Templates

Write tests for your templates:

```python
import pytest
from nexios.templating import TemplateEngine, TemplateConfig
from nexios.testing import TestClient

@pytest.fixture
def template_engine():
    config = TemplateConfig(template_dir="tests/templates")
    return TemplateEngine(config)

async def test_template_rendering(template_engine):
    content = await template_engine.render(
        "welcome.html",
        {"name": "User"}
    )
    assert "Welcome, User!" in content

async def test_template_filters(template_engine):
    content = await template_engine.render(
        "product.html",
        {"price": 99.99}
    )
    assert "€99.99" in content

async def test_context_middleware(client: TestClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Welcome, Test User!" in response.text
```
