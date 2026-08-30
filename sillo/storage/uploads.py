"""
sillo.storage.uploads — from a multipart upload into a bucket, without buffering.

The one place these two subsystems meet, and it needs a shim because they do not
quite fit: :class:`~sillo.objects.http.UploadedFile` exposes ``read(size)`` and
``seek``, while :meth:`~sillo.storage.bucket.Bucket.put` wants an async
iterator. Without something here, every project writes the same six-line
generator, and about half of them write ``await upload.read()`` instead — which
pulls the whole file into memory and quietly undoes the reason ``put`` takes a
stream at all.

The parser has already spooled the body to disk, so reading it back in chunks
never assembles it: an upload of any size crosses into a bucket in
:data:`CHUNK`-sized pieces.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

__all__ = ["CHUNK", "stream_upload"]

#: How much is read from the spooled upload at a time.
CHUNK = 64 * 1024


async def stream_upload(
    upload: Any, *, chunk_size: int = CHUNK
) -> AsyncIterator[bytes]:
    """Stream a multipart upload.

    Rewinds first. A handler that has already inspected the upload — checked a
    magic number, measured it — leaves the cursor somewhere in the middle, and
    storing from there writes a truncated file with no error anywhere.

    Args:
        upload: An ``UploadedFile`` from ``await ctx.files``, or anything
            else with async ``read`` and ``seek``.
        chunk_size: How much to read at a time.

    Yields:
        The content, in chunks.

    Example:
        ```python
        files = await ctx.files
        upload = files["document"]

        await bucket.put(
            f"documents/{upload.filename}",
            stream_upload(upload),
            content_type=upload.content_type or "",
            user=ctx.user,
        )
        ```
    """
    seek = getattr(upload, "seek", None)
    if seek is not None:
        await seek(0)

    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        yield chunk
