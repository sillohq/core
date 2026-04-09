from datetime import datetime

import humanize
import markdown2

from nexios import NexiosApp
from nexios.templating import TemplateConfig, render

app = NexiosApp()


def format_datetime(value, format="%Y-%m-%d %H:%M"):
    """Custom filter to format datetime objects."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(format)


def humanize_number(value):
    """Custom filter to humanize numbers."""
    return humanize.intcomma(value)


def markdown_to_html(value):
    """Custom filter to convert markdown to HTML."""
    return markdown2.markdown(value)


# Configure templating with custom filters and globals
template_config = TemplateConfig(
    template_dir="templates",
    custom_filters={
        "datetime": format_datetime,
        "humanize": humanize_number,
        "markdown": markdown_to_html,
    },
    custom_globals={
        "site_name": "Nexios Demo",
        "current_year": datetime.now().year,
        "version": "1.0.0",
    },
)

app.config.templating = template_config


@app.get("/blog")
async def blog_list(request, response):
    """Example using custom filters and globals."""
    posts = [
        {
            "title": "Getting Started with Nexios",
            "content": """
# Getting Started
Nexios is a modern web framework that makes it easy to build web applications.
- Fast
- Secure
- Easy to use
            """,
            "views": 12345,
            "published": "2024-03-15T10:30:00",
        },
        {
            "title": "Advanced Templating",
            "content": """
# Advanced Templates
Learn how to use advanced templating features:
1. Custom filters
2. Global variables
3. Markdown support
            """,
            "views": 5432,
            "published": "2024-03-16T15:45:00",
        },
    ]

    return await render("blog/list.html", {"posts": posts})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

"""
Example template (blog/list.html):
{% extends 'base.html' %}

{% block content %}
    <h1>{{ site_name }} Blog</h1>
    
    {% for post in posts %}
    <article class="post">
        <h2>{{ post.title }}</h2>
        <div class="metadata">
            Published: {{ post.published|datetime('%B %d, %Y') }}
            <br>
            Views: {{ post.views|humanize }}
        </div>
        <div class="content">
            {{ post.content|markdown }}
        </div>
    </article>
    {% endfor %}
    
    <footer>
        <p>{{ site_name }} v{{ version }} - © {{ current_year }}</p>
    </footer>
{% endblock %}
"""
