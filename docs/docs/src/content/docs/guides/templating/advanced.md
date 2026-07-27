---
title: Advanced Templating
icon: template
description: Custom filters and globals, macros, async templates, layered context processors, fragment caching, error templates, and testing rendered output.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Advanced Templating
  - tag: meta
    attrs:
      property: og:description
      content: Custom filters and globals, macros, async templates, layered context processors, fragment caching, error templates, and testing rendered output.
---
#  Advanced Templating

This guide covers advanced features and patterns for the sillo templating system.

##  Custom Filters

A filter transforms a value on its way into the output. Register them
through `TemplateConfig` at setup so every template gets the same set,
rather than assigning to `env.filters` from scattered call sites.

```python
from sillo.templating import TemplateConfig

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

##  Macros

A macro is a template-level function: it takes arguments, returns markup,
and can be imported across files. Use one wherever you would otherwise
copy a block of HTML and change two attributes.

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

##  Async Template Functions

Create async template functions for database queries or API calls:

```python
from sillo.templating import TemplateConfig
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
{% for post in get_posts(user.id) %}
    <article>{{ post.title }}</article>
{% endfor %}
```

With `enable_async=True` — the default — Jinja2 awaits coroutines
automatically wherever a value is used. There is no `await` keyword in
template syntax; writing one is a `TemplateSyntaxError`.

##  Context Processors

Advanced context processor patterns:

```python
from typing import Dict, Any
from sillo.templating.middleware import template_context
# Use your preferred caching library for memoization

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

# Optional: add caching with your preferred library
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

app.use(template_context(
    context_processor=context_builder.build
))
```

##  Template Caching

:::caution[Prefer `sillo.cache` over a hand-rolled dict]
sillo ships a cache module — `MemoryCache`, `RedisCache`, a `@cache`
decorator, and key building — documented in [Cache](/guides/cache/). The
in-memory example below is only worth using when you deliberately want a
process-local cache with no dependencies; it has no size limit, no
eviction beyond expiry, and is not shared between workers.
:::

```python
from datetime import datetime, timedelta
from sillo.templating import TemplateConfig

_cache = {}

def cache_get(key: str):
    item = _cache.get(key)
    if not item:
        return None
    value, expires_at = item
    if datetime.utcnow() > expires_at:
        _cache.pop(key, None)
        return None
    return value

def cache_set(key: str, value, ttl: int = 300):
    _cache[key] = (value, datetime.utcnow() + timedelta(seconds=ttl))

config = TemplateConfig(
    custom_globals={
        "cache_get": cache_get,
        "cache_set": cache_set,
    }
)
```

Usage in templates:

```html
{% set cache_key = 'sidebar_' + user.id %}
{% set cached = cache_get(cache_key) %}
{% if cached %}
    {{ cached }}
{% else %}
    {% set content %}
        <aside>...</aside>
    {% endset %}
    {{ cache_set(cache_key, content, ttl=300) }}
    {{ content }}
{% endif %}
```


##  ⚠️ Error Handling

Custom error templates and handling:

```python
from sillo.templating import render
from jinja2 import TemplateError

@app.add_exception_handler(404)
async def not_found(request: Request, response: Response, exc: Exception):
    return await render(
        "errors/404.html",
        {"path": request.url.path},
        status_code=404
    )

@app.add_exception_handler(TemplateError)
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

##  Testing Templates

Templates fail in ways unit tests catch cheaply: a renamed context key, a
filter that raises on `None`, a macro whose signature changed. Test the
rendered string, not the HTML structure — assertions on exact markup
break on every styling change and teach people to delete tests.

```python
import pytest
from sillo.templating import TemplateEngine, TemplateConfig
from sillo.testclient import TestClient

@pytest.fixture
def template_engine():
    config = TemplateConfig(template_dir="tests/templates")
    engine = TemplateEngine()
    engine.setup_environment(config)
    return engine

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

---

##  Filters, tests, and globals — choosing between them

Jinja2 offers three extension points and they are not interchangeable.

A **filter** transforms a value: `{{ price|currency }}`. Use one when the
input is a value you already have and the output is a presentation of it.
Filters compose (`{{ text|truncate(50)|upper }}`) and read left to right,
which is why they suit formatting.

A **test** answers a question: `{% if user is subscriber %}`. Register
one when the condition appears in more than one template and reads badly
as an expression.

```python title="registering a test"
def is_subscriber(user) -> bool:
    return user is not None and user.plan in {"pro", "enterprise"}


engine.env.tests["subscriber"] = is_subscriber
```

A **global** is a function or value callable from anywhere:
`{{ get_posts(user.id) }}`. Use one when the template needs to *fetch*
something rather than transform something it was given.

The rule that keeps templates maintainable: filters and tests should be
pure and fast; globals may do work, and that work should be
deliberate. A global that queries the database is a query you cannot see
from the handler, which makes N+1 problems invisible until you read the
template.

##  Keeping logic out of templates

Every extension point above makes it easier to put logic in a template,
and templates are the worst place to keep it. They have no type checking,
no debugger worth the name, no unit tests unless you write them
specially, and errors that surface as a blank section rather than a
stack trace.

The line worth holding: **templates decide presentation, handlers decide
data.** A template may loop, format, and branch on a flag. It should not
compute a total, sort by a business rule, or decide whether a user is
allowed to see something.

```html title="too much logic in the template"
{% set visible = [] %}
{% for item in items %}
  {% if item.owner_id == user.id or user.is_admin %}
    {% set _ = visible.append(item) %}
  {% endif %}
{% endfor %}
{{ visible|length }} items
```

```python title="the same thing, testable"
visible = [i for i in items if i.owner_id == user.id or user.is_admin]
return await render("items.html", {"items": visible}, request=request)
```

The second version can be unit tested, reviewed as code, and reused by
the JSON version of the same endpoint. Authorization decisions especially
belong in Python — a permission check written in a template is a check
that no security review will find.

##  Debugging a template

Jinja2's errors are precise once you know how to read them.

`TemplateNotFound` names the template but not the search path. The loader
searches only `template_dir`, non-recursively by name — `{% extends "base.html" %}`
resolves relative to the template root, not to the current file's
directory. A partial in `templates/partials/nav.html` is
`{% include "partials/nav.html" %}`.

`UndefinedError: 'x' is undefined` means the variable was never in the
context. Most often the cause is a missing `request=request`, which
removes `url_for` and `csrf_token`, or a context processor that returned
early.

Silent blanks are the harder case. By default an undefined variable
renders as an empty string in an expression and only raises when you
operate on it, so `{{ user.nmae }}` shows nothing rather than
complaining. Switch to strict undefined behaviour in development to turn
those into errors:

```python title="fail loudly in development"
from jinja2 import StrictUndefined

engine.setup_environment(config)
if os.getenv("ENV") == "development":
    engine.env.undefined = StrictUndefined
```

That one line converts a class of invisible bugs — renamed context keys,
typo'd attribute names, forgotten processors — into immediate,
line-numbered failures.

##  Layout patterns that scale

Three structural decisions determine whether a template directory stays
navigable past thirty files.

**One base per page shape, not per page.** A marketing base, an
application base, and an email base is usually the complete set. Bases
that differ by one block should be one base with an overridable block.

```html title="templates/base.html"
<!DOCTYPE html>
<html>
  <head>
    <title>{% block title %}{{ site_name }}{% endblock %}</title>
    {% block head %}{% endblock %}
  </head>
  <body class="{% block body_class %}{% endblock %}">
    {% include "partials/nav.html" %}
    <main>{% block content %}{% endblock %}</main>
    {% block scripts %}{% endblock %}
  </body>
</html>
```

**Partials for markup, macros for parameterised markup.** An `include`
inherits the surrounding context implicitly, which is convenient and
makes dependencies invisible. A macro takes explicit arguments, which is
more typing and far easier to reason about. Use `include` for things that
genuinely need the whole context — navigation, flash messages — and
macros for anything you would otherwise pass variables to.

```html title="a macro with an explicit contract"
{% macro card(title, body, href=None) %}
  <article class="card">
    <h3>{% if href %}<a href="{{ href }}">{{ title }}</a>{% else %}{{ title }}{% endif %}</h3>
    <p>{{ body }}</p>
  </article>
{% endmacro %}
```

**Mirror your URL structure.** `templates/orders/detail.html` for
`/orders/{id}` means anyone can find the template from the route and the
route from the template. Flat directories stop working at about twenty
files.

Keep macros in `templates/macros/` and partials in `templates/partials/`
so the top level contains only pages. That single convention removes most
"where does this live" questions.

##  What not to do

**Do not put authorization logic in a template.** Security reviews read
Python.

**Do not query the database from a filter.** Filters run per value, in
loops.

**Do not use `await` in template syntax.** Async is automatic with
`enable_async`.

**Do not build cache keys from unsanitized user input** in a template.
The key ends up in shared storage.

**Do not catch `TemplateError` and render another template** without a
fallback — if the error template is the broken one, you have an infinite
loop.

**Do not rely on undefined variables rendering as blank.** Use
`StrictUndefined` in development.

**Do not compute in a template what a handler could compute.** You lose
tests, types, and reuse.

##  Performance notes

Filters run once per value. A `markdown` filter applied inside a loop
over a hundred rows parses Markdown a hundred times per request — render
it once when the content is written and store the HTML, or cache the
result keyed by content hash.

Globals that fetch data run per call site, and a call site inside a loop
runs per iteration. `{% for post in posts %}{{ get_author(post.id) }}{% endfor %}`
is an N+1 query that no database profiler will attribute to a handler,
because it happens during rendering. Prefetch in the handler.

Macros are compiled once with the template that defines them, so
importing a macro file from fifty templates costs one compilation.
`{% include %}` resolves at render time and hits the template cache each
time — cheap when cached, and another reason to size `cache_size`
correctly.

Fragment caching pays off when a fragment is expensive and shared across
users. It costs more than it saves when the fragment is per-user, because
you get one cache entry per user and a hit rate near zero. Cache the
shared sidebar, not the personalised greeting.

##  Related

- [Templating](/guides/templating/) — engine setup, autoescaping, and configuration
- [Cache](/guides/cache/) — the real cache module, for fragment and page caching
- [HTML helpers](/guides/helpers/html/) — escaping and why `sanitize_html` is not enough
- [CSRF](/guides/csrf/) — where `csrf_token` comes from
- [Error Handling](/guides/error-handling/) — registering the error handlers shown above
- [Static Files](/guides/static-files/) — serving the assets templates reference
