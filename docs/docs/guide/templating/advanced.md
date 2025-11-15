---
title: Advanced Templating
icon: template
description: >
    This guide covers advanced features and patterns for the Nexios templating system.
head:
  - - meta
    - property: og:title
      content: Advanced Templating
    - property: og:description
      content: This guide covers advanced features and patterns for the Nexios templating system.
---
# ⚡ Advanced Templating

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
{{ post.content|markdown }}
{{ product.price|currency("€") }}
```

## 🔧 Macros

Create reusable template components:

```html
{# macros/forms.html #}
{% macro input(name, value='', type='text', label='') %}
    <div class="form-group">
        {% if label %}
        <label for="{{ name }}">{{ label }}</label>
        {% endif %}
        <input type="{{ type }}" name="{{ name }}" 
               value="{{ value }}" id="{{ name }}">
    </div>
{% endmacro %}

{# Usage in templates #}
{% from "macros/forms.html" import input %}
<form method="post">
    {{ input('username', label='Username') }}
    {{ input('password', type='password', label='Password') }}
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
{% set posts = await get_posts(user.id) %}
{% for post in posts %}
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
{% set cache_key = 'sidebar_' + user.id %}
{% set cached = await cached_fragment(cache_key) %}
{% if cached %}
    {{ cached }}
{% else %}
    {% set content %}
        {# Expensive sidebar rendering #}
        <aside>...</aside>
    {% endset %}
    {{ cache.set(cache_key, content, ttl=300) }}
    {{ content }}
{% endif %}
```

## ⚠️ Error Handling

Custom error templates and handling:

```python
from nexios.templating import render
from nexios.exceptions import TemplateError

@app.app_exception_handler(404)
async def not_found(request: Request, response: Response, exc: Exception):
    return await render(
        "errors/404.html",
        {"path": request.url.path},
        status_code=404
    )

@app.app_exception_handler(TemplateError)
async def template_error(request: Request, response: Response, exc: Exception):
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