from __future__ import annotations

import mimetypes
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import List, Optional, Union


_SIZE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"]
_DANGEROUS_EXTENSIONS = frozenset(
    {
        "exe",
        "dll",
        "so",
        "sh",
        "bash",
        "bat",
        "cmd",
        "com",
        "php",
        "py",
        "rb",
        "pl",
        "js",
        "vbs",
        "ps1",
        "msi",
        "app",
    }
)
_SAFE_NAME_RE = re.compile(r"[^\w.\-]")
_EXT_RE = re.compile(r"\.([a-zA-Z0-9]+)$")


def format_size(bytes_value: Union[int, float]) -> str:
    """Format a byte count as a human-readable string using SI decimal units.

    Converts a numeric byte value into a compact, human-friendly string
    using base-1024 SI-style units (B, KB, MB, GB, TB, PB). Values are
    scaled down through each unit tier until the magnitude falls below
    1024, then formatted to one decimal place. Byte values below 1024
    are displayed as whole numbers without decimals.

    Args:
        bytes_value: The number of bytes to format. Can be an integer
            or floating-point value. Negative values are handled by
            using the absolute magnitude for unit selection.

    Returns:
        A formatted string such as ``"1.5 MB"`` or ``"512 B"``
        representing the human-readable size.
    """
    value = float(bytes_value)
    for unit in _SIZE_UNITS:
        if abs(value) < 1024.0:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{value:.1f} PB"


def format_size_binary(bytes_value: Union[int, float]) -> str:
    """Format a byte count as a human-readable string using IEC binary units.

    Converts a numeric byte value into a compact, human-friendly string
    using base-1024 IEC binary units (B, KiB, MiB, GiB, TiB, PiB). Values
    are scaled down through each unit tier until the magnitude falls below
    1024, then formatted to one decimal place. Byte values below 1024 are
    displayed as whole numbers without decimals.

    Args:
        bytes_value: The number of bytes to format. Can be an integer
            or floating-point value. Negative values are handled by
            using the absolute magnitude for unit selection.

    Returns:
        A formatted string such as ``"1.5 MiB"`` or ``"512 B"``
        representing the human-readable binary size.
    """
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    value = float(bytes_value)
    for unit in units:
        if abs(value) < 1024.0:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{value:.1f} PiB"


def parse_size(size_str: str) -> int:
    """Parse a human-readable size string into an integer byte count.

    Accepts size strings in common formats such as ``"10MB"``, ``"1.5 GB"``,
    or ``"512"`` (bare number treated as bytes). The numeric portion is
    extracted via regex and multiplied by the appropriate power-of-1024
    factor determined by the unit suffix. Unit matching is case-insensitive
    and supports both short and long forms (e.g. ``"k"`` and ``"kb"``).

    Args:
        size_str: A string containing a numeric value optionally followed
            by a unit suffix. Supported units: B, K/KB, M/MB, G/GB, T/TB.
            Whitespace between the number and unit is permitted.

    Returns:
        The parsed size as an integer number of bytes.

    Raises:
        ValueError: If the string does not match a valid size format
            (i.e. no leading numeric portion can be extracted).
    """
    units = {
        "b": 1,
        "k": 1024,
        "kb": 1024,
        "m": 1024**2,
        "mb": 1024**2,
        "g": 1024**3,
        "gb": 1024**3,
        "t": 1024**4,
        "tb": 1024**4,
    }
    match = re.match(r"^([\d.]+)\s*([a-zA-Z]*)", size_str.strip())
    if not match:
        raise ValueError(f"Invalid size string: {size_str}")
    value = float(match.group(1))
    unit = match.group(2).lower()
    multiplier = units.get(unit, 1)
    return int(value * multiplier)


def get_extension(filename: str) -> str:
    """Extract the file extension from a filename, including the leading dot.

    Splits the filename at the last dot and returns the extension portion
    in lowercase, including the leading period. If the filename has no
    extension, an empty string is returned.

    Args:
        filename: The filename or path string from which to extract the
            extension. Only the final path component's extension is used.

    Returns:
        The lowercase file extension including the leading dot (e.g.
        ``".txt"``), or an empty string if no extension is present.
    """
    return os.path.splitext(filename)[1].lower()


def get_extension_clean(filename: str) -> str:
    """Extract the file extension from a filename without the leading dot.

    Delegates to ``get_extension`` to obtain the lowercase extension and
    then strips the leading period character. Returns just the bare
    extension string suitable for comparison against extension lists.

    Args:
        filename: The filename or path string from which to extract the
            clean extension. Only the final path component is considered.

    Returns:
        The lowercase file extension without the leading dot (e.g.
        ``"txt"``), or an empty string if no extension is present.
    """
    ext = get_extension(filename)
    return ext.lstrip(".")


def guess_mime_type(filename: str) -> Optional[str]:
    """Guess the MIME type of a file based on its filename extension.

    Uses Python's ``mimetypes`` module to infer the MIME content type
    from the filename's extension. The lookup is performed against the
    system's MIME type database and any types known to the ``mimetypes``
    module.

    Args:
        filename: The filename or path string whose MIME type should be
            guessed. The extension is used for the lookup.

    Returns:
        The guessed MIME type string (e.g. ``"image/png"``), or ``None``
        if the extension is not recognized by the MIME type database.
    """
    mime, _ = mimetypes.guess_type(filename)
    return mime


def is_dangerous_extension(filename: str) -> bool:
    """Check whether a filename has a potentially dangerous file extension.

    Extracts the clean extension from the filename and checks it against
    a predefined frozenset of dangerous extensions that includes executable
    binaries, scripts, and other file types that could pose a security
    risk if served or executed unintentionally.

    Args:
        filename: The filename or path string to check. Only the final
            path component's extension is evaluated.

    Returns:
        ``True`` if the file extension is in the dangerous extensions set
        (e.g. ``"exe"``, ``"sh"``, ``"py"``), ``False`` otherwise.
    """
    ext = get_extension_clean(filename)
    return ext.lower() in _DANGEROUS_EXTENSIONS


def safe_filename(filename: str, replacement: str = "_") -> str:
    """Sanitize a filename by removing or replacing unsafe characters.

    Normalizes the filename to ASCII using NFKD Unicode normalization,
    strips non-word characters (except dots and hyphens) by replacing
    them with the specified replacement character, and ensures the
    result is not empty or a reserved directory name like ``"."`` or
    ``".."``.

    Args:
        filename: The raw filename string to sanitize. May contain
            Unicode characters, spaces, or special symbols.
        replacement: The character to substitute for unsafe characters.
            Defaults to ``"_"``.

    Returns:
        A sanitized filename string containing only ASCII word characters,
        dots, and hyphens. If the result would be empty or a reserved
        name, a ``"file"`` prefix is prepended.
    """
    name = unicodedata.normalize("NFKD", filename)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = _SAFE_NAME_RE.sub(replacement, name)
    name = name.strip(replacement)
    if not name or name in (".", ".."):
        name = f"file{name}"
    return name


def unique_filename(directory: Union[str, Path], filename: str) -> str:
    """Generate a unique filename within a directory by appending a counter.

    Checks whether the given filename already exists in the specified
    directory. If a collision is found, appends an incrementing integer
    counter in parentheses before the file extension (e.g. ``"file (1).txt"``)
    until a non-colliding name is found.

    Args:
        directory: The directory path as a string or ``Path`` object in
            which to check for filename collisions.
        filename: The desired filename string. May include an extension.

    Returns:
        The original filename if no collision exists, or a modified
        filename with an incrementing counter to ensure uniqueness.
    """
    base, ext = os.path.splitext(filename)
    counter = 1
    candidate = filename
    while os.path.exists(os.path.join(str(directory), candidate)):
        candidate = f"{base} ({counter}){ext}"
        counter += 1
    return candidate


def is_image_extension(filename: str) -> bool:
    """Check whether a filename has an image MIME type extension.

    Uses ``guess_mime_type`` to determine the MIME type of the filename
    and checks whether it falls under the ``"image/"`` top-level media
    type category.

    Args:
        filename: The filename or path string to check. The extension
            is used for MIME type inference.

    Returns:
        ``True`` if the guessed MIME type starts with ``"image/"``,
        ``False`` otherwise or if the MIME type cannot be determined.
    """
    mime = guess_mime_type(filename)
    return mime is not None and mime.startswith("image/")


def is_media_extension(filename: str) -> bool:
    """Check whether a filename has a media MIME type extension.

    Uses ``guess_mime_type`` to determine the MIME type of the filename
    and checks whether it falls under any of the media top-level types:
    ``"image/"``, ``"audio/"``, or ``"video/"``. This is a broader check
    than ``is_image_extension`` and covers all common media file types.

    Args:
        filename: The filename or path string to check. The extension
            is used for MIME type inference.

    Returns:
        ``True`` if the guessed MIME type starts with ``"image/"``,
        ``"audio/"``, or ``"video/"``, ``False`` otherwise or if the
        MIME type cannot be determined.
    """
    mime = guess_mime_type(filename)
    if mime is None:
        return False
    return mime.startswith(("image/", "audio/", "video/"))


def file_age(path: Union[str, Path]) -> float:
    """Calculate the age of a file in seconds since its last modification.

    Retrieves the last modification timestamp of the file at the given
    path using ``os.path.getmtime`` and computes the elapsed time since
    then relative to the current system time.

    Args:
        path: The file path as a string or ``Path`` object. The file
            must exist; otherwise an ``OSError`` is raised by the OS.

    Returns:
        The age of the file in seconds as a floating-point number,
        representing the time elapsed since the last modification.

    Raises:
        OSError: If the file does not exist or is inaccessible.
    """
    return time.time() - os.path.getmtime(str(path))


def file_age_human(path: Union[str, Path]) -> str:
    """Calculate the age of a file and return it as a human-friendly string.

    Computes the file's age in seconds via ``file_age`` and converts it
    to the most appropriate human-readable time unit: seconds (``"s ago"``),
    minutes (``"m ago"``), hours (``"h ago"``), or days (``"d ago"``).
    The value is truncated to an integer at each tier boundary.

    Args:
        path: The file path as a string or ``Path`` object. The file
            must exist; otherwise an ``OSError`` is raised by ``file_age``.

    Returns:
        A human-readable age string such as ``"5s ago"``, ``"12m ago"``,
        ``"3h ago"``, or ``"7d ago"``.

    Raises:
        OSError: If the file does not exist or is inaccessible.
    """
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
    """Create a directory and all intermediate parent directories if needed.

    Ensures that the specified directory path exists by creating it along
    with any missing parent directories. If the directory already exists,
    no error is raised. Uses ``parents=True`` and ``exist_ok=True`` to
    make the operation idempotent.

    Args:
        path: The directory path as a string or ``Path`` object to
            create. May include nested parent directories.

    Returns:
        A ``Path`` object pointing to the ensured directory.

    Raises:
        OSError: If the directory cannot be created due to permission
            errors or other filesystem issues.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_files(
    directory: Union[str, Path],
    pattern: str = "*",
    recursive: bool = False,
) -> List[Path]:
    """List files in a directory matching a glob pattern.

    Scans the specified directory for files matching the given glob
    pattern. Supports both flat and recursive directory traversal.
    In recursive mode, ``rglob`` is used to match files at all depth
    levels; in flat mode, only immediate children are matched.

    Args:
        directory: The directory path as a string or ``Path`` object
            to scan for matching files.
        pattern: A glob pattern string to filter results. Defaults
            to ``"*"`` which matches all entries. Supports standard
            glob wildcards such as ``"*.txt"`` or ``"**/*.py"``.
        recursive: If ``True``, traverse subdirectories recursively
            using ``Path.rglob``. If ``False``, only list immediate
            children using ``Path.glob``. Defaults to ``False``.

    Returns:
        A list of ``Path`` objects for all files matching the pattern
        within the specified directory scope.
    """
    p = Path(directory)
    if recursive:
        return list(p.rglob(pattern))
    return list(p.glob(pattern))
