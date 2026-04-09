from pathlib import Path

from nexios import NexiosApp
from nexios.templating import TemplateConfig, render

app = NexiosApp()

# Configure templating with inheritance support
template_config = TemplateConfig(
    template_dir=Path("templates"),
    trim_blocks=True,  # Clean whitespace handling
    lstrip_blocks=True,  # Clean whitespace handling
)

app.config.templating = template_config


@app.get("/")
async def home(request, response):
    """Render home page using template inheritance."""
    return await render(
        "pages/home.html",
        {
            "title": "Home",
            "content": "Welcome to our site!",
            "features": [
                {"name": "Fast", "description": "Built for speed"},
                {"name": "Secure", "description": "Security first"},
                {"name": "Modern", "description": "Using latest tech"},
            ],
        },
    )


@app.get("/blog/{post_id}")
async def blog_post(request, response, post_id: int):
    """Demonstrate filter usage in templates."""
    post = {
        "id": post_id,
        "title": "Understanding Nexios Templates",
        "content": "This is a **markdown** post about templates.",
        "author": "nexios team",
        "published": "2024-03-15T10:30:00",
        "tags": ["python", "web", "templates"],
    }

    return await render("pages/blog_post.html", {"title": post["title"], "post": post})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

"""
Example template structure:

templates/
    base.html           # Base template with common structure
    components/
        header.html     # Reusable header component
        footer.html     # Reusable footer component
    pages/
        home.html       # Home page extending base.html
        blog_post.html  # Blog post page extending base.html

Example base.html:
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }} - Nexios</title>
</head>
<body>
    {% include 'components/header.html' %}
    
    <main>
        {% block content %}{% endblock %}
    </main>
    
    {% include 'components/footer.html' %}
</body>
</html>

Example pages/home.html:
{% extends 'base.html' %}

{% block content %}
    <h1>{{ title }}</h1>
    <p>{{ content }}</p>
    
    <div class="features">
    {% for feature in features %}
        <div class="feature">
            <h3>{{ feature.name }}</h3>
            <p>{{ feature.description }}</p>
        </div>
    {% endfor %}
    </div>
{% endblock %}

Example pages/blog_post.html:
{% extends 'base.html' %}

{% block content %}
    <article>
        <h1>{{ post.title }}</h1>
        <div class="metadata">
            By {{ post.author|title }} on {{ post.published|datetime('%B %d, %Y') }}
        </div>
        <div class="content">
            {{ post.content|markdown }}
        </div>
        <div class="tags">
            {% for tag in post.tags %}
                <span class="tag">{{ tag }}</span>
            {% endfor %}
        </div>
    </article>
{% endblock %}
"""
