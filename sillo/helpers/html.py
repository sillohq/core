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
    """Escape special HTML characters in a string for safe rendering.

    Converts characters such as ``&``, ``<``, ``>``, ``"``, and ``'``
    into their corresponding HTML entity representations so that the
    resulting string can be safely embedded inside HTML content without
    introducing markup errors or cross-site scripting vectors.

    Args:
        text: The raw text string to be HTML-escaped.

    Returns:
        A new string with all special HTML characters replaced by
        their safe entity equivalents.
    """
    return _html.escape(text, quote=True)


def unescape_html(text: str) -> str:
    """Convert HTML entities back to their corresponding Unicode characters.

    Reverses the escaping process by translating HTML entity references
    such as ``&amp;``, ``&lt;``, ``&gt;``, ``&quot;``, and ``&#39;`` back
    into their original character forms. This is useful when processing
    previously escaped HTML content for display or further manipulation
    in a non-HTML context such as plain-text rendering or data export.

    Args:
        text: A string potentially containing HTML entity references
            that should be converted back to raw characters.

    Returns:
        A new string with all recognized HTML entities replaced by
        their corresponding Unicode characters.
    """
    return _html.unescape(text)


def strip_tags(html: str) -> str:
    """Remove all HTML tags from a string while preserving inner text content.

    Parses the provided HTML string using a dedicated ``HTMLParser`` subclass
    and extracts only the textual data between tags, discarding all markup.
    This is particularly useful for generating plain-text previews, computing
    text-based lengths, or sanitizing user-supplied content before further
    processing where no HTML structure should remain.

    Args:
        html: A string containing HTML markup from which all tags
            should be removed.

    Returns:
        A plain-text string with all HTML tags stripped out, leaving
        only the concatenated text data that was between the tags.
    """

    class Stripper(HTMLParser):
        """Internal HTML parser subclass that collects only text data.

        This parser feeds through an HTML document and accumulates
        all encountered text data while ignoring every tag, attribute,
        and structural element. The collected text fragments are stored
        in an internal list for later joining into a single string.
        """

        def __init__(self):
            super().__init__()
            self.result: List[str] = []

        def handle_data(self, data):
            """Append a chunk of raw text data encountered in the HTML.

            This callback is invoked by the ``HTMLParser`` base class
            whenever textual content is found between HTML tags. Each
            fragment is appended to the internal result list.

            Args:
                data: The text content extracted from between HTML tags.
            """
            self.result.append(data)

    s = Stripper()
    s.feed(html)
    return "".join(s.result)


def sanitize_html(
    html: str,
    allowed_tags: Optional[set[str] | frozenset[str]] = None,
    allowed_attrs: Optional[set[str] | frozenset[str]] = None,
    strip: bool = True,
) -> str:
    """Sanitize an HTML string by removing disallowed tags and dangerous attributes.

    Strips out XSS attack vectors such as ``javascript:`` URIs, inline event
    handlers, ``data:`` URIs, and ``vbscript:`` URIs. When ``strip`` is enabled,
    only tags present in the allowed set are retained and their attributes are
    filtered against the allowed attribute set. All other tags are removed
    entirely from the output.

    Args:
        html: The raw HTML string to sanitize.
        allowed_tags: An optional set of tag names that should be preserved.
            Defaults to a built-in safe set including common formatting tags.
        allowed_attrs: An optional set of attribute names that are permitted
            on retained tags. Defaults to a built-in safe set.
        strip: If True, disallowed tags are removed from the output entirely.
            If False, only XSS patterns are stripped and the HTML is returned
            with its original tag structure intact.

    Returns:
        The sanitized HTML string with dangerous content removed and
        only allowed tags and attributes preserved.
    """
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
    """Render a dictionary of attributes into a safe HTML attribute string.

    Takes a mapping of attribute names to values and produces a properly
    escaped string suitable for inclusion inside an HTML opening tag. Both
    keys and values are HTML-escaped to prevent injection attacks, and
    attribute keys are lowercased for consistency with HTML conventions.

    Args:
        attrs: A dictionary mapping attribute names to their string values.
            Keys are lowercased and both keys and values are HTML-escaped.

    Returns:
        A space-separated string of escaped ``key="value"`` pairs ready
        for insertion into an HTML tag.
    """
    parts = []
    for key, value in attrs.items():
        safe_value = escape_html(str(value))
        safe_key = key.lower()
        parts.append(f'{_html.escape(safe_key)}="{safe_value}"')
    return " ".join(parts)


def generate_safe_id(text: str) -> str:
    """Generate a safe HTML-compatible identifier from an arbitrary text string.

    Transforms the input text into a slug-style identifier by lowercasing,
    replacing spaces with hyphens, and stripping all characters that are not
    word characters or hyphens. Consecutive hyphens are collapsed and leading
    or trailing hyphens are removed. If the result is empty or begins with a
    digit, a ``id-`` prefix is prepended to ensure validity as an HTML id.

    Args:
        text: The raw text string to convert into a safe identifier.
            Spaces are replaced with hyphens and non-word characters
            are removed.

    Returns:
        A sanitized string suitable for use as an HTML ``id`` attribute
        value, guaranteed to start with a letter.
    """
    safe = re.sub(r"[^\w\-]", "", text.lower().replace(" ", "-"))
    safe = re.sub(r"-+", "-", safe).strip("-")
    if not safe or safe[0].isdigit():
        safe = "id-" + safe
    return safe


def linkify(text: str) -> str:
    """Convert plain-text URLs in a string into clickable HTML anchor links.

    Scans the input text for substrings that match common HTTP and HTTPS URL
    patterns and wraps each match in an ``<a>`` tag. Generated links include
    ``rel="noopener noreferrer"`` and ``target="_blank"`` attributes to ensure
    safe opening in a new browser tab without exposing the originating page
    to reverse tab-nabbing attacks.

    Args:
        text: A plain-text string that may contain one or more URLs
            to be converted into clickable HTML anchor elements.

    Returns:
        A new string where every detected URL has been replaced with
        an HTML ``<a>`` tag linking to that URL.
    """
    url_pattern = re.compile(r'(https?://[^\s<>"\'\)\[\]{}|\\^`]+)')
    return url_pattern.sub(
        r'<a href="\1" rel="noopener noreferrer" target="_blank">\1</a>', text
    )
