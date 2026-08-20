"""
Getting a multipart upload into a bucket.

The parser spools the body to disk, so reading it back in chunks never
assembles it — which is the whole point, and is why this is a helper rather
than something every project writes for itself.
"""

from __future__ import annotations

import pytest

from sillo.storage import Bucket, MemoryDriver, Public, stream_upload
from sillo.storage.base import collect


class Spooled:
    """Stands in for an UploadedFile: async read and seek over a buffer."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.position = 0
        self.reads = 0

    async def read(self, size: int = -1) -> bytes:
        self.reads += 1
        if size < 0:
            chunk, self.position = self.data[self.position :], len(self.data)
            return chunk

        chunk = self.data[self.position : self.position + size]
        self.position += len(chunk)
        return chunk

    async def seek(self, offset: int) -> None:
        self.position = offset


class TestStreaming:
    async def test_the_whole_upload_arrives(self):
        upload = Spooled(b"hello there")
        assert await collect(stream_upload(upload)) == b"hello there"

    async def test_it_arrives_in_chunks(self):
        """Not in one read, which would be the thing this exists to prevent."""
        upload = Spooled(b"x" * 10_000)
        chunks = [chunk async for chunk in stream_upload(upload, chunk_size=1024)]

        assert len(chunks) > 1
        assert b"".join(chunks) == b"x" * 10_000

    async def test_an_already_read_upload_is_rewound(self):
        """A handler that inspected the upload leaves the cursor mid-file, and
        storing from there writes a truncated object with no error anywhere."""
        upload = Spooled(b"hello there")
        await upload.read(6)

        assert await collect(stream_upload(upload)) == b"hello there"

    async def test_an_empty_upload_yields_nothing(self):
        assert await collect(stream_upload(Spooled(b""))) == b""

    async def test_something_without_seek_still_streams(self):
        class NoSeek:
            def __init__(self):
                self.done = False

            async def read(self, size=-1):
                if self.done:
                    return b""
                self.done = True
                return b"data"

        assert await collect(stream_upload(NoSeek())) == b"data"

    async def test_it_goes_into_a_bucket(self):
        bucket = Bucket("uploads", MemoryDriver(), policy=Public())
        upload = Spooled(b"name,email\na,b\n")

        stored = await bucket.put(
            "exports/people.csv",
            stream_upload(upload),
            content_type="text/csv",
            signed=True,
        )

        assert stored.size == 15
        assert stored.content_type == "text/csv"

    async def test_a_large_upload_is_not_read_in_one_go(self):
        bucket = Bucket("uploads", MemoryDriver(), policy=Public())
        upload = Spooled(b"y" * 500_000)

        await bucket.put("big.bin", stream_upload(upload, chunk_size=8192), signed=True)

        # Roughly 500_000 / 8192 reads plus the final empty one.
        assert upload.reads > 50
