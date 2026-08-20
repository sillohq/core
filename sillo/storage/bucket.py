"""
sillo.storage.bucket — the object a project actually holds.

A :class:`Bucket` is a driver with the four things a driver deliberately does
not know about wrapped around it: the policy, the sniffer, the size limit, and
the event.

Keeping those out of the drivers is what makes the contract suite meaningful.
A driver's job is to move bytes; if it also decided what a file was and who
could have it, every backend would get its own chance to decide differently.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from .base import Action, Driver, FileInfo, Page, StorageEvent, Stored
from .errors import PolicyRefused, StorageError
from .paths import normalise
from .policies import BucketPolicy, Private
from .sniff import PROBE_BYTES, sniff

__all__ = ["Bucket"]


class Bucket:
    """One named place to put things, with rules.

    Attributes:
        name: What the project calls it.
        driver: Where the bytes go.
        policy: Who may do what.
        max_bytes: Largest object accepted. Zero for no limit.
        accepts: Content types accepted after sniffing. Empty for anything.
    """

    __slots__ = ("accepts", "driver", "max_bytes", "name", "policy")

    def __init__(
        self,
        name: str,
        driver: Driver,
        *,
        policy: BucketPolicy | None = None,
        max_bytes: int = 0,
        accepts: tuple[str, ...] = (),
    ) -> None:
        """Build a bucket.

        Args:
            name: What to call it.
            driver: Where the bytes go.
            policy: Who may do what. Private when unset.
            max_bytes: Largest object accepted.
            accepts: Content types accepted, after sniffing.
        """
        self.name = name
        self.driver = driver
        self.policy = policy or Private()
        self.max_bytes = max_bytes
        self.accepts = accepts

    # -- reading and writing --------------------------------------------

    async def put(
        self,
        key: str,
        stream: AsyncIterator[bytes],
        *,
        content_type: str = "",
        user: Any = None,
        signed: bool = False,
    ) -> Stored:
        """Store an object.

        The stream is consumed once.  The first :data:`~sillo.storage.sniff.PROBE_BYTES`
        are held back to identify the content and then put in front of the rest,
        so identification costs one small buffer rather than the whole file.

        Args:
            key: Where to put it.
            stream: The content.
            content_type: What the uploader claimed. Recorded, never trusted.
            user: Who is asking.
            signed: Whether a valid signature already authorised this.

        Returns:
            What was written.

        Raises:
            PolicyRefused: If the policy declines.
            StorageError: If the object is too large, or is a type this bucket
                does not accept.
        """
        key = normalise(key)
        self._permit(Action.WRITE, key, user, signed)

        started = time.perf_counter()

        # Read enough to identify the content, but never more than the bucket
        # will accept. Without the second half, a bucket limited to a kilobyte
        # still reads four before refusing — which is harmless for a file and
        # wrong in principle, since the limit is what the caller asked to be
        # enforced.
        probe = (
            PROBE_BYTES if not self.max_bytes else min(PROBE_BYTES, self.max_bytes + 1)
        )
        head, rest = await _peek(stream, probe)
        resolved = sniff(head, declared=content_type, key=key)

        if self.accepts and resolved not in self.accepts:
            await self._record(key, Action.WRITE, started, outcome="error")
            raise StorageError(
                f"{self.name} does not accept {resolved}; it accepts "
                f"{', '.join(self.accepts)}"
            )

        try:
            stored = await self.driver.write(
                key,
                _capped(head, rest, self.max_bytes),
                content_type=resolved,
                declared_type=content_type,
            )
        except Exception as error:
            await self._record(key, Action.WRITE, started, outcome="error", error=error)
            raise

        await self._record(key, Action.WRITE, started, size=stored.size)
        return stored

    async def get(
        self, key: str, *, user: Any = None, signed: bool = False
    ) -> AsyncIterator[bytes]:
        """Stream an object back.

        Args:
            key: The object's key.
            user: Who is asking.
            signed: Whether a valid signature already authorised this.

        Yields:
            The content, in chunks.

        Raises:
            PolicyRefused: If the policy declines.
            FileNotFound: If there is no such object.
        """
        key = normalise(key)
        self._permit(Action.READ, key, user, signed)

        started = time.perf_counter()
        sent = 0

        async for chunk in self.driver.read(key):
            sent += len(chunk)
            yield chunk

        await self._record(key, Action.READ, started, size=sent)

    async def stat(
        self, key: str, *, user: Any = None, signed: bool = False
    ) -> FileInfo:
        """Describe one object.

        Args:
            key: The object's key.
            user: Who is asking.
            signed: Whether a valid signature already authorised this.

        Returns:
            What is known about it.
        """
        key = normalise(key)
        self._permit(Action.READ, key, user, signed)
        return await self.driver.stat(key)

    async def exists(self, key: str, *, user: Any = None) -> bool:
        """Whether an object is there.

        Args:
            key: The object's key.
            user: Who is asking.

        Returns:
            True when it exists.
        """
        key = normalise(key)
        self._permit(Action.READ, key, user, False)
        return await self.driver.exists(key)

    async def delete(self, key: str, *, user: Any = None, signed: bool = False) -> bool:
        """Remove one object.

        Args:
            key: The object's key.
            user: Who is asking.
            signed: Whether a valid signature already authorised this.

        Returns:
            Whether anything was removed.
        """
        key = normalise(key)
        self._permit(Action.DELETE, key, user, signed)

        started = time.perf_counter()
        removed = await self.driver.delete(key)

        await self._record(
            key, Action.DELETE, started, outcome="ok" if removed else "missing"
        )
        return removed

    async def page(
        self,
        prefix: str = "",
        *,
        cursor: str = "",
        limit: int = 100,
        user: Any = None,
    ) -> Page:
        """List one page of objects.

        Args:
            prefix: Only keys starting with this.
            cursor: Where to resume.
            limit: Most objects to return.
            user: Who is asking.

        Returns:
            The page.
        """
        self._permit(Action.LIST, prefix, user, False)

        started = time.perf_counter()
        page = await self.driver.page(prefix, cursor=cursor, limit=limit)

        await self._record(prefix, Action.LIST, started, size=len(page.files))
        return page

    def signed_url(
        self,
        key: str,
        *,
        method: str = "GET",
        expires_in: int = 300,
        content_type: str = "",
        max_bytes: int = 0,
    ) -> str:
        """A URL granting one narrow permission for a while.

        Args:
            key: The object's key.
            method: The single permitted method.
            expires_in: Seconds until it stops working.
            content_type: The single permitted content type.
            max_bytes: The largest permitted body. Falls back to the bucket's
                own limit, so a signed upload slot is never wider than the
                bucket itself.

        Returns:
            The URL.

        Raises:
            PolicyRefused: If the policy will not honour a signature for this.
        """
        key = normalise(key)
        action = Action.READ if method.upper() == "GET" else Action.WRITE

        if not self.policy.signable(action):
            raise PolicyRefused(action.value, key)

        return self.driver.signed_url(
            key,
            method=method,
            expires_in=expires_in,
            content_type=content_type,
            max_bytes=max_bytes or self.max_bytes,
        )

    # -- internals ------------------------------------------------------

    def _permit(self, action: Action, key: str, user: Any, signed: bool) -> None:
        """Check the policy, or raise.

        Args:
            action: What is being attempted.
            key: On what.
            user: Who is asking.
            signed: Whether a valid signature already authorised this.

        Raises:
            PolicyRefused: If neither the signature nor the user suffices.
        """
        if signed and self.policy.signable(action):
            return

        if not self.policy.allows(action, key, user):
            raise PolicyRefused(action.value, key)

    async def _record(
        self,
        key: str,
        action: Action,
        started: float,
        *,
        size: int = 0,
        outcome: str = "ok",
        error: Exception | None = None,
    ) -> None:
        """Tell anything watching what happened.

        Args:
            key: What was operated on.
            action: What was done.
            started: ``perf_counter`` reading from before it.
            size: Bytes moved.
            outcome: How it went.
            error: What went wrong, when something did.
        """
        await self.driver.emit(
            StorageEvent(
                bucket=self.name,
                key=key,
                action=action,
                driver=self.driver.name,
                size=size,
                duration_ms=(time.perf_counter() - started) * 1000,
                outcome=outcome,
                error=f"{type(error).__name__}: {error}" if error else "",
            )
        )

    def __repr__(self) -> str:
        """A short description for debugging.

        Returns:
            The name, driver and policy.
        """
        return (
            f"Bucket({self.name!r}, driver={self.driver.name}, policy={self.policy!r})"
        )


async def _peek(
    stream: AsyncIterator[bytes], want: int
) -> tuple[bytes, AsyncIterator[bytes]]:
    """Read enough of a stream to identify it, without losing it.

    Args:
        stream: The content.
        want: How much to read.

    Returns:
        The leading bytes, and the remainder of the stream.
    """
    head = bytearray()

    async for chunk in stream:
        head.extend(chunk)
        if len(head) >= want:
            break

    return bytes(head), stream


async def _capped(
    head: bytes, rest: AsyncIterator[bytes], limit: int
) -> AsyncIterator[bytes]:
    """Put the peeked bytes back in front, and stop at the limit.

    The limit is enforced *while streaming*, not by checking a declared
    ``Content-Length`` — which is a number the uploader chose. A body that
    claims one megabyte and sends a hundred is refused at the megabyte, having
    buffered none of it.

    Args:
        head: What was read to identify the content.
        rest: The remainder of the stream.
        limit: Most bytes to accept. Zero for no limit.

    Yields:
        The whole content.

    Raises:
        StorageError: If the limit is exceeded.
    """
    sent = 0

    for piece in (head,):
        if piece:
            sent += len(piece)
            _check(sent, limit)
            yield piece

    async for chunk in rest:
        sent += len(chunk)
        _check(sent, limit)
        yield chunk


def _check(sent: int, limit: int) -> None:
    """Refuse a stream that has grown past its limit.

    Args:
        sent: How much has passed.
        limit: The ceiling, or zero.

    Raises:
        StorageError: If the ceiling is passed.
    """
    if limit and sent > limit:
        raise StorageError(f"object exceeds the bucket's limit of {limit} bytes")
