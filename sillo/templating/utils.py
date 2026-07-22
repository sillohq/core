"""
Template utility functions.
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union


def static_hash(filepath: str) -> str:
    """Generate an MD5 content hash for cache-busting static files.

    Reads the file at *filepath*, computes its MD5 digest, and returns
    the first 8 hex characters. Returns an empty string if the file does
    not exist.

    Args:
        filepath: Absolute or relative path to the static file.

    Returns:
        An 8-character hex string (truncated MD5) or ``""`` if the
        file is missing. Intended for use in template URLs like
        ``style.css?v=<hash>``.
    """
    if not os.path.exists(filepath):
        return ""
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


def format_datetime(value: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a ``datetime`` object as a string using the given format.

    Thin wrapper around ``strftime`` for use inside Jinja2 templates.

    Args:
        value: The ``datetime`` instance to format.
        fmt: A ``strftime``-compatible format string. Defaults to
            ``"%Y-%m-%d %H:%M:%S"``.

    Returns:
        The formatted date-time string.
    """
    return value.strftime(fmt)


def truncate(text: str, length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length, breaking at word boundaries.

    If *text* exceeds *length*, it is trimmed to the nearest word break
    before the limit and the *suffix* is appended. Short text is returned
    unchanged.

    Args:
        text: The input string to truncate.
        length: Maximum character count before truncation. Default 100.
        suffix: String appended when truncation occurs. Default ``"..."``.

    Returns:
        The original text if short enough, or a word-broken truncated
        version with the suffix appended.
    """
    if len(text) <= length:
        return text
    return text[:length].rsplit(" ", 1)[0] + suffix


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two or more dictionaries into a single dictionary.

    Later dictionaries take precedence over earlier ones for duplicate
    keys.  Returns a new dict; the inputs are not mutated.

    Args:
        *dicts: One or more dictionaries to merge.

    Returns:
        A new dictionary containing all key-value pairs from every
        input, with later values overriding earlier ones.
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


def get_template_globals() -> Dict[str, Any]:
    """Return the default dictionary of template-global callables.

    These functions are injected into every template context so they can
    be used directly in Jinja2 templates without explicit passing:
    ``{{ static_hash(...) }}``, ``{{ format_datetime(...) }}``, etc.

    Returns:
        A dict mapping names (``now``, ``static_hash``,
        ``format_datetime``, ``truncate``) to their corresponding
        utility functions.
    """
    return {
        "now": datetime.now,
        "static_hash": static_hash,
        "format_datetime": format_datetime,
        "truncate": truncate,
    }


def create_template_dir(template_dir: Optional[Union[str, Path]] = None) -> Path:
    """Ensure a template directory exists and return its ``Path``.

    Creates the directory (including parents) if it does not already
    exist.  Defaults to ``"templates"`` in the current working directory.

    Args:
        template_dir: Path to the template directory. If ``None``,
            defaults to ``"templates"``.

    Returns:
        A ``Path`` object pointing to the (now-existing) directory.
    """
    template_dir = Path(template_dir or "templates")
    template_dir.mkdir(parents=True, exist_ok=True)
    return template_dir
