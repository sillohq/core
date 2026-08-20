"""
sillo.storage.drivers.local — objects as files, contained by resolution.

The driver a project starts with, and the one that has to be paranoid: a key
arrives from outside and becomes a path.  Containment is checked by resolving
and comparing against the root — never by looking for ``..`` in the input, which
misses encodings, misses symlinks, and misses whatever is invented next.

Writes go to a temporary file in the same directory and are renamed into place.
On a POSIX filesystem that rename is atomic, so a reader never sees a half-
written object and a crash mid-upload leaves the previous version intact rather
than a truncated one.  Object storage gets this property for free; a filesystem
has to be asked for it.
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from pathlib import Path

import anyio

from ..base import Driver, FileInfo, Page, Stored
from ..errors import FileNotFound
from ..paths import contain
from ..signing import SignedGrant, Signer

__all__ = ["LocalDriver"]

#: How much is read from disk at a time.
CHUNK = 64 * 1024

#: Where a content type is remembered.
#:
#: A filesystem has nowhere to put it — there is no metadata slot on a file —
#: so it lives in an extended attribute where the platform has them and in a
#: sidecar where it does not. The sniffed type must survive a restart; deciding
#: it again on read would mean reading the file to serve the file.
XATTR = "user.sillo.content_type"


class LocalDriver(Driver):
    """Objects stored as files under one directory.

    Attributes:
        root: The bucket's directory.
        base_url: Where the serving route is mounted, for signed URLs.
    """

    name = "local"

    def __init__(
        self,
        root: str | Path,
        *,
        signer: Signer | None = None,
        base_url: str = "",
    ) -> None:
        """Build the driver.

        Args:
            root: The directory to store under. Created if absent.
            signer: What mints signed URLs. Without one the driver works and
                cannot sign, and says so when asked.
            base_url: Where the serving route is mounted.
        """
        super().__init__()
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url.rstrip("/")
        self._signer = signer

    def _path(self, key: str) -> Path:
        """Where a key lives.

        Args:
            key: A normalised key.

        Returns:
            The absolute path.

        Raises:
            UnsafeKey: If it resolves outside the root.
        """
        return contain(self.root, key)

    async def write(
        self,
        key: str,
        stream: AsyncIterator[bytes],
        *,
        content_type: str = "",
        declared_type: str = "",
    ) -> Stored:
        """Write an object atomically.

        Args:
            key: Where to put it.
            stream: The content.
            content_type: What to serve it as.
            declared_type: What the uploader claimed.

        Returns:
            What was written.
        """
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)

        # Beside the target, not in /tmp: a rename across filesystems is a copy,
        # and a copy is not atomic.
        staging = target.with_name(f".{target.name}.{os.getpid()}.partial")

        written = 0
        try:
            async with await anyio.open_file(staging, "wb") as handle:
                async for chunk in stream:
                    await handle.write(chunk)
                    written += len(chunk)

            resolved = content_type or "application/octet-stream"

            # The extended attribute goes on the staging file, so it arrives
            # with the rename. The sidecar is named for the *target*, because
            # the staging name is about to stop existing — naming it for the
            # staging file is why the first version lost every content type on
            # any filesystem without xattrs, which is all of macOS.
            _remember_type(staging, target, resolved)
            staging.replace(target)
        except BaseException:
            staging.unlink(missing_ok=True)
            raise

        return Stored(key, written, resolved, _etag(target))

    async def read(self, key: str) -> AsyncIterator[bytes]:
        """Stream an object back.

        Args:
            key: The object's key.

        Yields:
            The content, in chunks.

        Raises:
            FileNotFound: If there is no such object.
        """
        path = self._path(key)

        if not path.is_file():
            raise FileNotFound(key)

        async with await anyio.open_file(path, "rb") as handle:
            while True:
                chunk = await handle.read(CHUNK)
                if not chunk:
                    break
                yield chunk

    async def stat(self, key: str) -> FileInfo:
        """Describe one object.

        Args:
            key: The object's key.

        Returns:
            What is known about it.

        Raises:
            FileNotFound: If there is no such object.
        """
        path = self._path(key)

        if not path.is_file():
            raise FileNotFound(key)

        stat = path.stat()

        return FileInfo(
            key=key,
            size=stat.st_size,
            content_type=_recall_type(path),
            modified=stat.st_mtime,
            etag=_etag(path),
        )

    async def delete(self, key: str) -> bool:
        """Remove one object, and any directory it emptied.

        Args:
            key: The object's key.

        Returns:
            Whether anything was removed.
        """
        path = self._path(key)

        if not path.is_file():
            return False

        path.unlink()
        _forget_type(path)
        _prune(path.parent, self.root.resolve())

        return True

    async def page(
        self, prefix: str = "", *, cursor: str = "", limit: int = 100
    ) -> Page:
        """List one page of objects.

        Args:
            prefix: Only keys starting with this.
            cursor: Where to resume.
            limit: Most objects to return.

        Returns:
            The page.
        """
        root = self.root.resolve()
        keys = sorted(
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_file() and not path.name.startswith(".")
        )

        keys = [key for key in keys if key.startswith(prefix)]
        if cursor:
            keys = [key for key in keys if key > cursor]

        window = keys[:limit]
        following = keys[limit : limit + 1]

        # A loop, not a generator expression: `tuple(await ... for ...)` builds
        # an async generator and hands it to tuple(), which cannot iterate it.
        files = []
        for key in window:
            files.append(await self.stat(key))

        return Page(
            files=tuple(files),
            prefixes=_prefixes(keys, prefix),
            cursor=window[-1] if following and window else "",
        )

    def signed_url(
        self,
        key: str,
        *,
        method: str = "GET",
        expires_in: int = 300,
        content_type: str = "",
        max_bytes: int = 0,
    ) -> str:
        """A URL the serving route will honour.

        Args:
            key: The object's key.
            method: The single permitted method.
            expires_in: Seconds until it stops working.
            content_type: The single permitted content type.
            max_bytes: The largest permitted body.

        Returns:
            The URL.

        Raises:
            NotImplementedError: If the driver was built without a signer.
        """
        if self._signer is None:
            raise NotImplementedError(
                "this LocalDriver has no signer. setup_storage() gives one to "
                "every bucket; a hand-built driver needs Signer(secret)."
            )

        token = self._signer.sign(
            SignedGrant(
                key=key,
                method=method,
                expires=time.time() + expires_in,
                content_type=content_type,
                max_bytes=max_bytes,
            )
        )

        return f"{self.base_url}/{key}?token={token}"

    async def capabilities(self) -> dict[str, object]:
        """What this driver can do here.

        Returns:
            Capability names to values.
        """
        found = await super().capabilities()
        found.update(
            {
                "signed_urls": self._signer is not None,
                "atomic_write": True,
                "content_type_metadata": _xattrs_work(self.root),
            }
        )
        return found

    async def close(self) -> None:
        """Nothing to release."""


def _etag(path: Path) -> str:
    """A cheap version marker.

    Size and modification time rather than a hash of the content: hashing means
    reading the whole file, and an etag is wanted on every ``stat``.

    Args:
        path: The file.

    Returns:
        The marker.
    """
    stat = path.stat()
    return f"{stat.st_size:x}-{int(stat.st_mtime_ns):x}"


def _remember_type(staging: Path, target: Path, content_type: str) -> None:
    """Record a file's content type.

    Args:
        staging: The file as written, before the rename.
        target: Where it is about to land, which is what a sidecar is named
            for — the staging name is about to stop existing.
        content_type: What it will be served as.
    """
    try:
        os.setxattr(staging, XATTR, content_type.encode())  # type: ignore[attr-defined]
        return
    except (AttributeError, OSError):
        # No extended attributes here — a different filesystem, or a platform
        # without them at all, which includes macOS. A sidecar is uglier and
        # works everywhere.
        pass

    _sidecar(target).write_text(content_type, encoding="utf-8")


def _recall_type(path: Path) -> str:
    """Read back a file's content type.

    Args:
        path: The file.

    Returns:
        What it was stored as, or the neutral fallback.
    """
    try:
        return os.getxattr(path, XATTR).decode()  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

    sidecar = _sidecar(path)
    if sidecar.is_file():
        return sidecar.read_text(encoding="utf-8").strip()

    return "application/octet-stream"


def _forget_type(path: Path) -> None:
    """Remove any sidecar left beside a deleted file.

    Args:
        path: The file that was deleted.
    """
    _sidecar(path).unlink(missing_ok=True)


def _sidecar(path: Path) -> Path:
    """Where a file's type is written when the filesystem cannot hold it.

    Dot-prefixed so that :meth:`LocalDriver.page` skips it — a sidecar is not
    an object and must never appear in a listing.

    Args:
        path: The file.

    Returns:
        The sidecar's path.
    """
    return path.with_name(f".{path.name}.type")


def _xattrs_work(root: Path) -> bool:
    """Whether this filesystem holds extended attributes.

    Args:
        root: The bucket's directory.

    Returns:
        True when they work here.
    """
    probe = root / ".sillo-xattr-probe"
    try:
        probe.touch()
        os.setxattr(probe, XATTR, b"probe")  # type: ignore[attr-defined]
        return True
    except (AttributeError, OSError):
        return False
    finally:
        probe.unlink(missing_ok=True)


def _prune(directory: Path, root: Path) -> None:
    """Remove directories a delete left empty.

    Object storage has no directories, so a local bucket that accumulates empty
    ones diverges from every other backend in its listings.

    Args:
        directory: Where the deleted file was.
        root: The bucket's directory, which is never removed.
    """
    current = directory.resolve()

    while current != root and root in current.parents:
        try:
            next(current.iterdir())
            return
        except StopIteration:
            current.rmdir()
            current = current.parent
        except OSError:
            return


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
