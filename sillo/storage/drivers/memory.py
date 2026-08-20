"""
sillo.storage.drivers.memory — objects in a dictionary.

Exists for the contract suite first and for users second.  Every assertion the
suite makes runs against this driver, so it is the definition of what the
contract means; a backend that disagrees with it disagrees with the contract.

It is also what ``Storage.fake()`` hands you, which matters more than it looks.
The obvious way to build a test double for storage is to point the local driver
at a temporary directory — which is what most frameworks do, and which means an
application's storage tests only ever exercise filesystem semantics.  Every
difference that bites in production, starting with pagination, is invisible.
This one pages.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from ..base import Driver, FileInfo, Page, Stored
from ..errors import FileNotFound

__all__ = ["MemoryDriver"]


class MemoryDriver(Driver):
    """Objects held in a dictionary, for tests and for small ephemera."""

    name = "memory"

    def __init__(self) -> None:
        """Build an empty store."""
        super().__init__()
        self._objects: dict[str, tuple[bytes, FileInfo]] = {}

    async def write(
        self,
        key: str,
        stream: AsyncIterator[bytes],
        *,
        content_type: str = "",
        declared_type: str = "",
    ) -> Stored:
        """Write an object.

        Args:
            key: Where to put it.
            stream: The content.
            content_type: What to serve it as.
            declared_type: What the uploader claimed.

        Returns:
            What was written.
        """
        buffer = bytearray()
        async for chunk in stream:
            buffer.extend(chunk)

        info = FileInfo(
            key=key,
            size=len(buffer),
            content_type=content_type or "application/octet-stream",
            modified=time.time(),
            etag=f"{len(buffer)}-{hash(bytes(buffer)) & 0xFFFFFFFF:08x}",
            declared_type=declared_type,
        )
        self._objects[key] = (bytes(buffer), info)

        return Stored(key, info.size, info.content_type, info.etag)

    async def read(self, key: str) -> AsyncIterator[bytes]:
        """Stream an object back.

        Args:
            key: The object's key.

        Yields:
            The content, in one chunk.

        Raises:
            FileNotFound: If there is no such object.
        """
        found = self._objects.get(key)
        if found is None:
            raise FileNotFound(key)

        yield found[0]

    async def stat(self, key: str) -> FileInfo:
        """Describe one object.

        Args:
            key: The object's key.

        Returns:
            What is known about it.

        Raises:
            FileNotFound: If there is no such object.
        """
        found = self._objects.get(key)
        if found is None:
            raise FileNotFound(key)

        return found[1]

    async def delete(self, key: str) -> bool:
        """Remove one object.

        Args:
            key: The object's key.

        Returns:
            Whether anything was removed.
        """
        return self._objects.pop(key, None) is not None

    async def page(
        self, prefix: str = "", *, cursor: str = "", limit: int = 100
    ) -> Page:
        """List one page of objects.

        Paginated even though a dictionary need not be, because the point of
        this driver is to behave exactly like the contract — and a fake that is
        more permissive than production is a fake that hides the bug it was
        supposed to catch.

        Args:
            prefix: Only keys starting with this.
            cursor: Where to resume.
            limit: Most objects to return.

        Returns:
            The page.
        """
        keys = sorted(key for key in self._objects if key.startswith(prefix))
        if cursor:
            keys = [key for key in keys if key > cursor]

        window = keys[:limit]
        following = keys[limit : limit + 1]

        return Page(
            files=tuple(self._objects[key][1] for key in window),
            prefixes=_prefixes(keys, prefix),
            cursor=window[-1] if following and window else "",
        )

    async def close(self) -> None:
        """Discard everything."""
        self._objects.clear()


def _prefixes(keys: list[str], prefix: str) -> tuple[str, ...]:
    """The pseudo-directories directly under a prefix.

    Args:
        keys: Every matching key.
        prefix: What was asked for.

    Returns:
        The common prefixes, sorted.
    """
    found = set()

    for key in keys:
        rest = key[len(prefix) :]
        head, slash, _ = rest.partition("/")
        if slash:
            found.add(f"{prefix}{head}/")

    return tuple(sorted(found))
