---
title: HTML Helpers
description: HTML utilities — escape, sanitize, safe attributes, linkify.
---

# HTML (`sillo.helpers.html`)

```python
from sillo.helpers import html

html.escape_html('<script>alert("xss")</script>')
html.unescape_html("&lt;div&gt;")
html.strip_tags("<p>text <b>bold</b></p>")  # "text bold"
html.sanitize_html("<p onclick='xss'>safe</p>")  # "<p >safe</p>"
html.safe_attrs({"href": "https://x.com", "class": "btn"})
html.generate_safe_id("My Section!")       # "my-section"
html.linkify("Visit https://example.com")  # adds <a> tags
```
