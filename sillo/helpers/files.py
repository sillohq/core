from __future__ import annotations

import mimetypes
import os
import re
import unicodedata
from pathlib import Path
from typing import List, Optional, Union


_SIZE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"]
_DANGEROUS_EXTENSIONS = frozenset({
    "exe", "dll", "so", "sh", "bash", "bat", "cmd", "com",
    "php", "py", "rb", "pl", "js", "vbs", "ps1", "msi", "app",
})
_SAFE_NAME_RE = re.compile(r"[^\w.\-]")
_EXT_RE = re.compile(r"\.([a-zA-Z0-9]+)$")


def format_size(bytes_value: Union[int, float]) -> str:
    value = float(bytes_value)
    for unit in _SIZE_UNITS:
        if abs(value) < 1024.0:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{value:.1f} PB"


def format_size_binary(bytes_value: Union[int, float]) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    value = float(bytes_value)
    for unit in units:
        if abs(value) < 1024.0:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{value:.1f} PiB"


def parse_size(size_str: str) -> int:
    units = {"b": 1, "k": 1024, "kb": 1024, "m": 1024**2, "mb": 1024**2,
             "g": 1024**3, "gb": 1024**3, "t": 1024**4, "tb": 1024**4}
    match = re.match(r"^([\d.]+)\s*([a-zA-Z]*)", size_str.strip())
    if not match:
        raise ValueError(f"Invalid size string: {size_str}")
    value = float(match.group(1))
    unit = match.group(2).lower()
    multiplier = units.get(unit, 1)
    return int(value * multiplier)


def get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def get_extension_clean(filename: str) -> str:
    ext = get_extension(filename)
    return ext.lstrip(".")


def guess_mime_type(filename: str) -> Optional[str]:
    mime, _ = mimetypes.guess_type(filename)
    return mime


def is_dangerous_extension(filename: str) -> bool:
    ext = get_extension_clean(filename)
    return ext.lower() in _DANGEROUS_EXTENSIONS


def safe_filename(filename: str, replacement: str = "_") -> str:
    name = unicodedata.normalize("NFKD", filename)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = _SAFE_NAME_RE.sub(replacement, name)
    name = name.strip(replacement)
    if not name or name in (".", ".."):
        name = f"file{name}"
    return name


def unique_filename(directory: Union[str, Path], filename: str) -> str:
    base, ext = os.path.splitext(filename)
    counter = 1
    candidate = filename
    while os.path.exists(os.path.join(str(directory), candidate)):
        candidate = f"{base} ({counter}){ext}"
        counter += 1
    return candidate


def is_image_extension(filename: str) -> bool:
    mime = guess_mime_type(filename)
    return mime is not None and mime.startswith("image/")


def is_media_extension(filename: str) -> bool:
    mime = guess_mime_type(filename)
    if mime is None:
        return False
    return mime.startswith(("image/", "audio/", "video/"))


def file_age(path: Union[str, Path]) -> float:
    import time
    return time.time() - os.path.getmtime(str(path))


def file_age_human(path: Union[str, Path]) -> str:
    seconds = file_age(path)
    if seconds < 60:
        return f"{int(seconds)}s ago"
    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)}m ago"
    hours = minutes / 60
    if hours < 24:
        return f"{int(hours)}h ago"
    days = hours / 24
    return f"{int(days)}d ago"


def ensure_directory(path: Union[str, Path]) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_files(
    directory: Union[str, Path],
    pattern: str = "*",
    recursive: bool = False,
) -> List[Path]:
    p = Path(directory)
    if recursive:
        return list(p.rglob(pattern))
    return list(p.glob(pattern))
