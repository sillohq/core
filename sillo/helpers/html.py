from __future__ import annotations

import html as _html
import re
from html.parser import HTMLParser
from typing import Dict, List, Optional


_ALLOWED_TAGS_DEFAULT = frozenset(
    {"b", "i", "em", "strong", "a", "p", "br", "ul", "ol", "li", "code", "pre", "span"}
)
_ALLOWED_ATTRS_DEFAULT = frozenset({"href", "title", "class", "id", "target", "rel"})
_XSS_PATTERNS = [
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"data\s*:", re.IGNORECASE),
    re.compile(r"vbscript\s*:", re.IGNORECASE),
]
_ATTR_RE = re.compile(r'(\w+)\s*=\s*["\']([^"\']*)["\']')


def escape_html(text: str) -> str:
    return _html.escape(text, quote=True)


def unescape_html(text: str) -> str:
    return _html.unescape(text)


def strip_tags(html: str) -> str:
    class Stripper(HTMLParser):
        def __init__(self):
            super().__init__()
            self.result: List[str] = []

        def handle_data(self, data):
            self.result.append(data)

    s = Stripper()
    s.feed(html)
    return "".join(s.result)


def sanitize_html(
    html: str,
    allowed_tags: Optional[set] = None,
    allowed_attrs: Optional[set] = None,
    strip: bool = True,
) -> str:
    if allowed_tags is None:
        allowed_tags = _ALLOWED_TAGS_DEFAULT
    if allowed_attrs is None:
        allowed_attrs = _ALLOWED_ATTRS_DEFAULT

    for pattern in _XSS_PATTERNS:
        html = pattern.sub("", html)

    # Simple tag-based sanitization
    if strip:
        result = []
        i = 0
        while i < len(html):
            if html[i] == "<":
                end = html.find(">", i)
                if end == -1:
                    result.append(html[i:])
                    break
                tag_content = html[i + 1 : end]
                space_idx = tag_content.find(" ")
                tag_name = (
                    (tag_content[:space_idx] if space_idx != -1 else tag_content)
                    .lower()
                    .rstrip("/")
                )

                if tag_name in allowed_tags:
                    attrs = _ATTR_RE.findall(tag_content)
                    safe_attrs = " ".join(
                        f'{k}="{v}"'
                        for k, v in attrs
                        if k.lower() in allowed_attrs
                        and not any(p.search(v) for p in _XSS_PATTERNS)
                    )
                    result.append(
                        f"<{tag_name} {safe_attrs}>" if safe_attrs else f"<{tag_name}>"
                    )
                else:
                    result.append("")
                i = end + 1
            else:
                result.append(html[i])
                i += 1
        return "".join(result)

    return html


def safe_attrs(attrs: Dict[str, str]) -> str:
    parts = []
    for key, value in attrs.items():
        safe_value = escape_html(str(value))
        safe_key = key.lower()
        parts.append(f'{_html.escape(safe_key)}="{safe_value}"')
    return " ".join(parts)


def generate_safe_id(text: str) -> str:
    safe = re.sub(r"[^\w\-]", "", text.lower().replace(" ", "-"))
    safe = re.sub(r"-+", "-", safe).strip("-")
    if not safe or safe[0].isdigit():
        safe = "id-" + safe
    return safe


def linkify(text: str) -> str:
    url_pattern = re.compile(r'(https?://[^\s<>"\'\)\[\]{}|\\^`]+)')
    return url_pattern.sub(
        r'<a href="\1" rel="noopener noreferrer" target="_blank">\1</a>', text
    )
