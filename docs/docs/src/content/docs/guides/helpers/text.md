---
title: Text Helpers
description: Text utilities — truncate, excerpt, strip HTML, pluralize, word count, ellipsis.
---

# Text (`sillo.helpers.text`)

```python
from sillo.helpers import text

text.truncate("hello world", 8)               # "hello..."
text.strip_html("<p>hello <b>world</b></p>")  # "hello world"
text.excerpt("long text with query here...", "query", radius=20)
text.pluralize("box", 2)                      # "boxes"
text.pluralize("child", 2)                    # "children"
text.word_count("one two three")              # 3
text.ellipsis("line1\nline2\nline3\nline4", 2)  # "line1\nline2\n..."
text.wrap_text("long text...", width=40)
text.extract_urls("visit https://example.com")  # ["https://example.com"]
text.extract_emails("email me@test.com")       # ["me@test.com"]
```
