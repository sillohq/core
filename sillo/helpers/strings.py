from __future__ import annotations

import re
import secrets
import string as _string
import unicodedata
from typing import Optional

_CAMEL_TO_SNAKE_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_TO_SNAKE_RE2 = re.compile(r"([a-z\d])([A-Z])")
_SNAKE_TO_CAMEL_RE = re.compile(r"_([a-zA-Z\d])")
_SLUG_RE = re.compile(r"[^\w\s-]")
_SLUG_SPACE_RE = re.compile(r"[-\s]+")


def slugify(text: str, separator: str = "-") -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = _SLUG_RE.sub("", text).strip().lower()
    text = _SLUG_SPACE_RE.sub(separator, text)
    return text.strip(separator)


def camel_to_snake(name: str) -> str:
    name = _CAMEL_TO_SNAKE_RE.sub(r"\1_\2", name)
    name = _CAMEL_TO_SNAKE_RE2.sub(r"\1_\2", name)
    return name.lower()


def snake_to_camel(name: str, capitalize_first: bool = False) -> str:
    result = _SNAKE_TO_CAMEL_RE.sub(lambda m: m.group(1).upper(), name)
    if capitalize_first:
        result = result[0].upper() + result[1:] if result else result
    return result


def pascal_case(name: str) -> str:
    return snake_to_camel(name, capitalize_first=True)


def kebab_case(name: str) -> str:
    name = _CAMEL_TO_SNAKE_RE.sub(r"\1-\2", name)
    name = _CAMEL_TO_SNAKE_RE2.sub(r"\1-\2", name)
    return name.lower()


def mask_string(
    value: str,
    visible_start: int = 4,
    visible_end: int = 4,
    mask_char: str = "*",
) -> str:
    if len(value) <= visible_start + visible_end:
        return mask_char * len(value)
    return (
        value[:visible_start]
        + mask_char * (len(value) - visible_start - visible_end)
        + value[-visible_end:]
    )


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def random_string(
    length: int = 32,
    chars: Optional[str] = None,
) -> str:
    if chars is None:
        chars = _string.ascii_letters + _string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def random_digits(length: int = 6) -> str:
    return "".join(secrets.choice(_string.digits) for _ in range(length))


def random_token(length: int = 64) -> str:
    return secrets.token_urlsafe(length)


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def is_camel_case(text: str) -> bool:
    return text != text.lower() and text != text.upper() and "_" not in text


def is_snake_case(text: str) -> bool:
    return text == text.lower() and "_" in text and not text.startswith("_")
