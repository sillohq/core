"""
Template utility functions.
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union


def static_hash(filepath: str) -> str:
    """Generate file hash for cache busting."""
    if not os.path.exists(filepath):
        return ""
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


def format_datetime(value: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime with given format."""
    return value.strftime(fmt)


def truncate(text: str, length: int = 100, suffix: str = "...") -> str:
    """Truncate text to length."""
    if len(text) <= length:
        return text
    return text[:length].rsplit(" ", 1)[0] + suffix


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple dictionaries."""
    result = {}
    for d in dicts:
        result.update(d)
    return result


def get_template_globals() -> Dict[str, Any]:
    """Get default template globals."""
    return {
        "now": datetime.now,
        "static_hash": static_hash,
        "format_datetime": format_datetime,
        "truncate": truncate,
    }


def create_template_dir(template_dir: Optional[Union[str, Path]] = None) -> Path:
    """Create and return template directory."""
    template_dir = Path(template_dir or "templates")
    template_dir.mkdir(parents=True, exist_ok=True)
    return template_dir
