# Templating in Nexios

Nexios provides built-in support for Jinja2 templating, allowing you to generate dynamic HTML, XML, and other text-based content.

## Prerequisites

Before using templating features, install the required dependencies:

```bash
pip install nexios[templating]
```

This installs Jinja2, which is required for all templating functionality.

## Basic Usage

1. First, create a `templates` directory in your project root:

```
your_project/
??? main.py
??? templates/
    ??? index.html
```

2. Create a template file (e.g., `templates/index.html`):

```html
<!DOCTYPE html>
<html>
  <head>
    <title>{{ title }}</title>
  </head>
  <body>
    <h1>Hello, {{ name }}!</h1>
  </body>
</html>
```

3. In your Nexios application, render the template:

```python
from nexios import NexiosApp
from nexios.templating import TemplateEngine, render

app = NexiosApp()
engine = TemplateEngine()
engine.setup_environment()

@app.route("/")
async def home(request, response):
    return await render(
        "index.html",
        {"title": "Home", "name": "World"},
        request=request,
    )
```

::: tip
`render(...)` requires `TemplateEngine.setup_environment()` to be called first.
:::

## Available Features

### Template Inheritance

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html>
  <head>
    <title>{% block title %}My Site{% endblock %}</title>
  </head>
  <body>
    {% block content %}{% endblock %}
  </body>
</html>

<!-- templates/index.html -->
{% extends "base.html" %}
{% block title %}Home{% endblock %}
{% block content %}
<h1>Welcome to the Home Page</h1>
{% endblock %}
```

### Template Context Processors

You can add context processors to make variables available to all templates:

```python
from nexios.templating.middleware import template_context

async def site_name(request):
    return {"site_name": "My Awesome Site"}

app = NexiosApp()
engine = TemplateEngine()
engine.setup_environment()

app.add_middleware(template_context(
    context_processor=site_name,
    default_context={"version": "1.0.0"}
))
```

## Troubleshooting

If you encounter an error about Jinja2 not being found, make sure you've installed the templating extras:

```bash
pip install nexios[templating]
```

## Advanced Configuration

For more advanced Jinja2 configuration, use `TemplateConfig`:

```python
from nexios.templating import TemplateConfig

config = TemplateConfig(
    template_dir="templates",
    auto_reload=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

engine = TemplateEngine()
engine.setup_environment(config)
```
