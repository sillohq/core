"""
sillo.storage.base — the driver contract, and the shapes it deals in.

One contract over local disk and S3-compatible object storage. Everything else
in this package is either an implementation of it, a policy evaluated around it,
or a helper it uses; get these signatures right and the rest follows.

Four of them are deliberate, and each closes a failure this package exists to
avoid.

``put`` takes an async iterator and never bytes.  There is no ``put_bytes``
convenience, because the moment one exists every caller reaches for it and
"streamed uploads that never buffer a whole file" becomes a comment rather than
a property.  A caller who genuinely wants a whole file in memory can write the
two lines and own that decision.

``page`` is the only way to list.  S3 pages at a thousand keys and local disk
does not, so a contract returning a plain list is a contract where every project
works in development and falls over the first time a bucket grows.  Paging in
the signature makes that impossible to forget.

``signed_url`` is not optional.  Local disk cannot sign anything by itself, so
the honest alternatives were to let the method raise "unsupported" — which makes
"one contract" a lie and puts a branch in every project — or to make local
signing real.  It is real: an HMAC the framework mounts a route to verify.

``stat`` returns the *sniffed* content type.  The type a client declared is a
string the client chose, and it is recorded separately so the two can be
compared, but it is never what gets served.
"""

from __future__ import annotations

import abc
import dataclasses
import enum
import time
from collections.abc import AsyncIterator, Awaitable, Callable

__all__ = [
    "Action",
    "Driver",
    "FileInfo",
    "Listener",
    "Page",
    "StorageEvent",
    "Stored",
]


class Action(str, enum.Enum):
    """What is being done to an object.

    A ``str`` enum so it serialises without a conversion step, and so a policy
    can be written against the plain name.
    """

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    LIST = "list"


@dataclasses.dataclass(frozen=True, slots=True)
class FileInfo:
    """What is known about one stored object.

    Attributes:
        key: The object's key, normalised.
        size: Bytes stored.
        content_type: The type the object is *served* as, which is what the
            sniffer decided rather than what the uploader claimed.
        modified: Unix timestamp of the last write.
        etag: The backend's version marker, when it has one.
        declared_type: What the uploader said it was. Kept so the two can be
            compared and the mismatch reported; never used to serve.
    """

    key: str
    size: int
    content_type: str = "application/octet-stream"
    modified: float = 0.0
    etag: str = ""
    declared_type: str = ""

    @property
    def mistyped(self) -> bool:
        """Whether the uploader's claim disagreed with the content.

        Returns:
            True when a type was declared and the sniffer found another.
            Interesting on its own: a ``.png`` that is really HTML is the shape
            of a stored cross-site scripting attempt, not a mistake.
        """
        return bool(self.declared_type) and self.declared_type != self.content_type


@dataclasses.dataclass(frozen=True, slots=True)
class Stored:
    """The result of writing one object.

    Attributes:
        key: Where it went.
        size: How much was written.
        content_type: What it will be served as.
        etag: The backend's version marker, when it has one.
    """

    key: str
    size: int
    content_type: str
    etag: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class Page:
    """One page of a listing.

    Attributes:
        files: The objects on this page.
        prefixes: Common prefixes — the pseudo-directories a delimiter reveals.
        cursor: Where the next page starts, or an empty string at the end.
    """

    files: tuple[FileInfo, ...] = ()
    prefixes: tuple[str, ...] = ()
    cursor: str = ""

    @property
    def more(self) -> bool:
        """Whether another page follows.

        Returns:
            True when a cursor was returned.
        """
        return bool(self.cursor)


@dataclasses.dataclass(frozen=True, slots=True)
class StorageEvent:
    """One completed operation, for anything watching.

    Attributes:
        bucket: Which bucket.
        key: Which object, or the prefix for a listing.
        action: What was done.
        driver: The driver's short name.
        size: Bytes moved, where the operation moves any.
        duration_ms: How long it took.
        outcome: ``ok``, ``missing`` or ``error``.
        error: The message, when the outcome was an error.
    """

    bucket: str
    key: str
    action: Action
    driver: str
    size: int = 0
    duration_ms: float = 0.0
    outcome: str = "ok"
    error: str = ""
    at: float = dataclasses.field(default_factory=time.time)


#: Something that wants to be told about completed operations.
Listener = Callable[[StorageEvent], Awaitable[None] | None]


class Driver(abc.ABC):
    """A place objects can be put and got.

    Subclasses implement the six abstract methods.  Everything a driver has in
    common — event dispatch, the listener list, its own name — lives here, so
    that adding a backend is a matter of I/O and not of remembering to emit
    things.

    Attributes:
        name: Short lowercase name, used in events and by the interface.
    """

    name: str = "driver"

    def __init__(self) -> None:
        """Build a driver with nothing listening."""
        self._listeners: list[Listener] = []

    # -- the contract ---------------------------------------------------

    @abc.abstractmethod
    async def write(
        self,
        key: str,
        stream: AsyncIterator[bytes],
        *,
        content_type: str = "",
        declared_type: str = "",
    ) -> Stored:
        """Write an object, consuming *stream* as it goes.

        Args:
            key: Where to put it, already normalised.
            stream: The content. Consumed once, never materialised whole.
            content_type: What to serve it as, already decided by the sniffer.
            declared_type: What the uploader claimed, recorded for comparison.

        Returns:
            What was written.
        """

    @abc.abstractmethod
    def read(self, key: str) -> AsyncIterator[bytes]:
        """Stream an object back.

        Not a coroutine: it returns the iterator directly, so ``async for``
        works without an intermediate ``await``.

        Args:
            key: The object's key.

        Returns:
            The content, in chunks.

        Raises:
            FileNotFound: If there is no such object.
        """

    @abc.abstractmethod
    async def stat(self, key: str) -> FileInfo:
        """Describe one object.

        Args:
            key: The object's key.

        Returns:
            What is known about it.

        Raises:
            FileNotFound: If there is no such object.
        """

    @abc.abstractmethod
    async def delete(self, key: str) -> bool:
        """Remove one object.

        Args:
            key: The object's key.

        Returns:
            True when something was removed, False when there was nothing to
            remove. Deleting an absent object is not an error — the caller's
            intent is satisfied either way.
        """

    @abc.abstractmethod
    async def page(
        self, prefix: str = "", *, cursor: str = "", limit: int = 100
    ) -> Page:
        """List one page of objects under a prefix.

        Args:
            prefix: Only keys starting with this.
            cursor: Where to resume, from a previous page.
            limit: Most objects to return.

        Returns:
            The page, and where the next one starts.
        """

    @abc.abstractmethod
    async def close(self) -> None:
        """Release whatever the driver is holding."""

    # -- provided -------------------------------------------------------

    async def exists(self, key: str) -> bool:
        """Whether an object is there.

        Args:
            key: The object's key.

        Returns:
            True when it exists.
        """
        from .errors import FileNotFound

        try:
            await self.stat(key)
        except FileNotFound:
            return False
        return True

    async def copy(self, source: str, target: str) -> Stored:
        """Copy one object to another key.

        The default streams through this process, which is correct everywhere
        and wasteful against a backend that can copy server-side. Drivers that
        can should override it; the contract suite runs the same assertions
        either way.

        Args:
            source: The key to copy from.
            target: The key to copy to.

        Returns:
            What was written.
        """
        info = await self.stat(source)
        return await self.write(
            target,
            self.read(source),
            content_type=info.content_type,
            declared_type=info.declared_type,
        )

    async def move(self, source: str, target: str) -> Stored:
        """Move one object to another key.

        Args:
            source: The key to move from.
            target: The key to move to.

        Returns:
            What was written.
        """
        stored = await self.copy(source, target)
        await self.delete(source)
        return stored

    def signed_url(
        self,
        key: str,
        *,
        method: str = "GET",
        expires_in: int = 300,
        content_type: str = "",
        max_bytes: int = 0,
    ) -> str:
        """A URL that grants one narrow permission for a while.

        Args:
            key: The object's key.
            method: The single HTTP method the URL permits.
            expires_in: Seconds until it stops working.
            content_type: The single content type a write may carry.
            max_bytes: The largest body a write may carry.

        Returns:
            The URL.

        Raises:
            NotImplementedError: If the driver was built without the means to
                sign. Every shipped driver can; a third-party one that cannot
                should say so here rather than returning something that does
                not work.
        """
        raise NotImplementedError(
            f"{type(self).__name__} cannot sign URLs. Configure it with a "
            "signer, or use a driver that can."
        )

    async def capabilities(self) -> dict[str, object]:
        """What this driver, against this endpoint, can actually do.

        Answered by asking rather than by assuming, because "S3-compatible"
        is a spectrum and a hardcoded table ages into a lie. ``vise doctor``
        prints this; a driver reads it to choose an upload strategy.

        Returns:
            Capability names to values.
        """
        return {
            "driver": self.name,
            "signed_urls": type(self).signed_url is not Driver.signed_url,
            "server_side_copy": type(self).copy is not Driver.copy,
        }

    # -- watching -------------------------------------------------------

    def listen(self, listener: Listener) -> Listener:
        """Be told about every completed operation.

        This exists in version one on purpose.  Every other sillo subsystem
        that something wanted to watch — queries, cache, outgoing calls, queues,
        schedules, events — offered no hook, so the tooling wraps private
        methods on six different classes, and two of those seams turned out to
        be the wrong ones in ways nothing reported.  A storage operation is I/O
        measured in milliseconds; one attribute check per call is free here in a
        way it is not on the request path.

        Args:
            listener: Called with each :class:`StorageEvent`.

        Returns:
            The listener, so this can be used as a decorator.
        """
        self._listeners.append(listener)
        return listener

    def unlisten(self, listener: Listener) -> None:
        """Stop telling *listener* about operations.

        Args:
            listener: The listener to drop.
        """
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def emit(self, event: StorageEvent) -> None:
        """Tell every listener about one operation.

        A listener that raises is dropped from consideration for that event and
        nothing else: an observer must not be able to fail a write.

        Args:
            event: What happened.
        """
        if not self._listeners:
            return

        for listener in tuple(self._listeners):
            try:
                result = listener(event)
                if result is not None:
                    await result
            except Exception:
                continue

    def __repr__(self) -> str:
        """A short description for debugging.

        Returns:
            The driver's name.
        """
        return f"{type(self).__name__}(name={self.name!r})"


async def chunks(data: bytes, size: int = 64 * 1024) -> AsyncIterator[bytes]:
    """Turn bytes into a stream.

    The one place the package builds a stream out of a whole buffer, so that
    tests and small writes have something to pass to :meth:`Driver.write`
    without every caller inventing it.

    Args:
        data: The content.
        size: Chunk size.

    Yields:
        The content, in chunks.
    """
    for start in range(0, len(data) or 1, size):
        piece = data[start : start + size]
        if piece or not data:
            yield piece


async def collect(stream: AsyncIterator[bytes], limit: int = 0) -> bytes:
    """Read a stream into memory.

    Deliberately explicit, and deliberately takes a limit.  Calling this is a
    decision to buffer, and the signature makes the caller state how much they
    are willing to buffer.

    Args:
        stream: The content.
        limit: Most bytes to read. Zero means no limit.

    Returns:
        The content.

    Raises:
        ValueError: If *limit* is exceeded.
    """
    buffer = bytearray()

    async for chunk in stream:
        buffer.extend(chunk)
        if limit and len(buffer) > limit:
            raise ValueError(f"stream exceeded {limit} bytes")

    return bytes(buffer)
