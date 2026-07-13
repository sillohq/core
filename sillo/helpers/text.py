from __future__ import annotations

import re
import typing
from html.parser import HTMLParser as _HTMLParser

_HTML_TAG_RE = re.compile(r"<[^>]*>")
_MULTI_SPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"\w+")
_PLURAL_IRREGULARS = {
    "child": "children",
    "man": "men",
    "woman": "women",
    "person": "people",
    "mouse": "mice",
    "goose": "geese",
    "tooth": "teeth",
    "foot": "feet",
    "ox": "oxen",
    "crisis": "crises",
    "analysis": "analyses",
    "phenomenon": "phenomena",
    "criterion": "criteria",
    "datum": "data",
}


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)].rstrip() + suffix


def excerpt(text: str, query: str, radius: int = 50) -> str:
    stripped = strip_html(text)
    idx = stripped.lower().find(query.lower())
    if idx == -1:
        return truncate(stripped, radius * 2)
    start = max(0, idx - radius)
    end = min(len(stripped), idx + len(query) + radius)
    result = stripped[start:end]
    if start > 0:
        result = "..." + result
    if end < len(stripped):
        result = result + "..."
    return result


def strip_html(text: str) -> str:
    return _MULTI_SPACE_RE.sub(" ", _HTML_TAG_RE.sub(" ", text)).strip()


def pluralize(word: str, count: int) -> str:
    if count == 1:
        return word
    word_lower = word.lower()
    if word_lower in _PLURAL_IRREGULARS:
        return _PLURAL_IRREGULARS[word_lower]

    if word_lower.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word_lower.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word_lower.endswith("f") and word_lower not in ("roof", "chief", "belief"):
        return word[:-1] + "ves"
    if word_lower.endswith("fe"):
        return word[:-2] + "ves"
    return word + "s"


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def ellipsis(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + "\n..."


def wrap_text(text: str, width: int = 80) -> str:
    words = text.split()
    lines: typing.List[str] = []
    current: typing.List[str] = []
    current_len = 0
    for word in words:
        if current_len + len(word) + len(current) > width:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += len(word)
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def extract_urls(text: str) -> typing.List[str]:
    pattern = re.compile(
        r'https?://[^\s<>"\'\)\[\]{}|\\^`]+'
    )
    return pattern.findall(text)


def extract_emails(text: str) -> typing.List[str]:
    pattern = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
    return pattern.findall(text)
