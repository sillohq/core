"""
sillo.storage.paths — one canonical key form, and containment by construction.

Object storage has keys and filesystems have paths, and the differences are
exactly where the bugs live.  ``a//b`` and ``a/b`` are the same file on disk and
two different keys on S3.  ``./a`` is ``a`` on disk and a literal key beginning
with a dot on S3.  A driver that normalises differently from its neighbour is a
driver whose behaviour changes when a project switches backend.

So every key goes through :func:`normalise` before it reaches any driver, and
the drivers themselves never re-interpret it.

Containment is checked by *resolving* and comparing, never by looking for ``..``
in the input.  Filtering for ``..`` misses percent-encoding, misses backslashes
on the wrong platform, misses symlinks entirely, and misses whatever is invented
next.  Resolution is the property that actually has to hold.
"""

from __future__ import annotations

import posixpath
import unicodedata
from pathlib import Path

from .errors import UnsafeKey

__all__ = ["contain", "join", "normalise", "parent", "segments"]

#: The longest key any backend here will accept. S3 allows 1024 bytes; a
#: filesystem is usually stricter per component. Refusing early keeps the two
#: backends behaving the same.
MAX_KEY_BYTES = 1024

#: The longest single path component.
MAX_SEGMENT = 255

#: Characters no key may contain. Control characters break HTTP headers and
#: some filesystems; a backslash is a separator on one platform and a literal
#: on another, and a key that means two things is not a key.
_FORBIDDEN = frozenset({"\\", "\x00"})


def normalise(key: str) -> str:
    """Reduce a key to the one form every driver will see.

    Args:
        key: The key as the caller wrote it.

    Returns:
        The canonical form: no leading slash, no ``.`` or ``..`` components, no
        repeated slashes, Unicode in NFC.

    Raises:
        UnsafeKey: If the key is empty, absolute, too long, contains a
            forbidden character, or climbs above the root.
    """
    if not key or not key.strip():
        raise UnsafeKey("a key cannot be empty")

    # NFC first, so that two spellings of the same name are one key. Without
    # this a macOS upload and a Linux upload of "café.pdf" are different
    # objects that look identical in every listing.
    key = unicodedata.normalize("NFC", key)

    if any(character in _FORBIDDEN for character in key):
        raise UnsafeKey(f"{key!r} contains a character no key may hold")

    if any(ord(character) < 32 or ord(character) == 127 for character in key):
        raise UnsafeKey(f"{key!r} contains a control character")

    if key.startswith("/"):
        raise UnsafeKey(f"{key!r} is absolute; keys are relative to the bucket")

    # posixpath rather than pathlib: a key is always slash-separated whatever
    # the host platform does, and pathlib would helpfully reinterpret it.
    cleaned = posixpath.normpath(key)

    if cleaned in (".", "/") or cleaned.startswith("../") or cleaned == "..":
        raise UnsafeKey(f"{key!r} climbs above the bucket")

    cleaned = cleaned.lstrip("/")

    if len(cleaned.encode("utf-8")) > MAX_KEY_BYTES:
        raise UnsafeKey(f"key is longer than {MAX_KEY_BYTES} bytes")

    if any(len(part.encode("utf-8")) > MAX_SEGMENT for part in cleaned.split("/")):
        raise UnsafeKey(f"a path segment is longer than {MAX_SEGMENT} bytes")

    return cleaned


def segments(key: str) -> tuple[str, ...]:
    """Split a normalised key into its parts.

    Args:
        key: A normalised key.

    Returns:
        The segments.
    """
    return tuple(part for part in key.split("/") if part)


def parent(key: str) -> str:
    """The prefix a key sits under.

    Args:
        key: A normalised key.

    Returns:
        Everything before the last segment, with a trailing slash, or an empty
        string at the top level.
    """
    head, _, _ = key.rpartition("/")
    return f"{head}/" if head else ""


def join(*parts: str) -> str:
    """Join key parts and normalise the result.

    Args:
        *parts: Key fragments.

    Returns:
        One normalised key.

    Raises:
        UnsafeKey: If the result is not a safe key.
    """
    return normalise("/".join(part.strip("/") for part in parts if part))


def contain(root: Path, key: str) -> Path:
    """Turn a key into a path inside *root*, or refuse.

    The containment check is the point.  ``resolve()`` follows symlinks and
    collapses everything, and the result either is inside the root or is not —
    a property that holds regardless of how the input was spelled.

    Args:
        root: The bucket's directory.
        key: A normalised key.

    Returns:
        The absolute path the key names.

    Raises:
        UnsafeKey: If the resolved path is outside *root*.
    """
    base = root.resolve()
    target = (base / key).resolve()

    if target != base and base not in target.parents:
        raise UnsafeKey(f"{key!r} resolves outside the bucket")

    return target
