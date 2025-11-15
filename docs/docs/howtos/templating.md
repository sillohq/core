# Templating in Nexios

Nexios provides built-in support for Jinja2 templating, allowing you to easily generate dynamic HTML, XML, and other text-based content.

## Prerequisites

Before using templating features, you need to install the required dependencies:

```bash
pip install nexios[templating]
```

This will install Jinja2, which is required for all templating functionality.

## Basic Usage

1. First, create a `templates` directory in your project root:

   ```
   your_project/
   ├── main.py
   └── templates/
       └── index.html
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

3. In your Nexios application, use the template:

   ```python
   from nexios import Nexios
   from nexios.templating import Jinja2Templates
   from nexios.http import HTMLResponse

   app = Nexios()
   templates = Jinja2Templates(directory="templates")

   @app.route("/")
   async def home(request):
       return templates.TemplateResponse("index.html", {"request": request, "title": "Home", "name": "World"})
   ```

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
{% extends "base.html" %} {% block title %}Home{% endblock %} {% block content
%}
<h1>Welcome to the Home Page</h1>
{% endblock %}
```

### Template Context Processors

You can add context processors to make variables available to all templates:

```python
def site_name():
    return {"site_name": "My Awesome Site"}

app = Nexios()
templates = Jinja2Templates(
    directory="templates",
    context_processors=[site_name, other_processor]
)
```

## Troubleshooting

If you encounter an error about Jinja2 not being found, make sure you've installed the templating extras:

```bash
pip install nexios[templating]
```

## Advanced Configuration

For more advanced Jinja2 configuration, you can pass additional options to the `Jinja2Templates` constructor:

```python
templates = Jinja2Templates(
    directory="templates",
    autoescape=True,
    auto_reload=True,  # Auto-reload templates in development
    trim_blocks=True,
    lstrip_blocks=True
)
```
