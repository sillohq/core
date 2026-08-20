"""
The bucket: policy, limits, sniffing and events, around a driver.

The driver's job is to move bytes. Everything here is what the bucket adds, and
it is tested separately because a driver that also decided what a file was and
who could have it would give every backend its own chance to decide differently.
"""

from __future__ import annotations

import tracemalloc

import anyio
import pytest

from sillo.storage import Bucket, MemoryDriver, Owned, Private, Public, ReadOnly
from sillo.storage.base import Action, chunks, collect
from sillo.storage.errors import PolicyRefused, StorageError, UnsafeKey


class User:
    """Somebody signed in."""

    is_authenticated = True

    def __init__(self, identity: str = "114") -> None:
        self.identity = identity


ANON = None


@pytest.fixture
def bucket():
    return Bucket("attachments", MemoryDriver(), policy=Public())


class TestPolicy:
    async def test_a_private_bucket_refuses_a_signed_in_user(self):
        """Private means private, not "private unless you are logged in"."""
        held = Bucket("secret", MemoryDriver(), policy=Private())

        with pytest.raises(PolicyRefused):
            await held.put("a.txt", chunks(b"x"), user=User())

    async def test_a_private_bucket_honours_a_signature(self):
        held = Bucket("secret", MemoryDriver(), policy=Private())
        await held.put("a.txt", chunks(b"x"), signed=True)

        assert await collect(held.get("a.txt", signed=True)) == b"x"

    async def test_a_private_bucket_still_refuses_the_same_read_unsigned(self):
        """Proving the previous test measures the signature and not a bucket
        that turned out to be readable anyway."""
        held = Bucket("secret", MemoryDriver(), policy=Private())
        await held.put("a.txt", chunks(b"x"), signed=True)

        with pytest.raises(PolicyRefused):
            await collect(held.get("a.txt", user=User()))

    async def test_a_public_bucket_reads_without_a_user(self, bucket):
        await bucket.put("a.txt", chunks(b"x"), signed=True)
        assert await collect(bucket.get("a.txt", user=ANON)) == b"x"

    async def test_a_public_bucket_still_refuses_an_anonymous_write(self, bucket):
        """"Public" elsewhere also means anybody who finds the URL may
        overwrite it, which is never what anybody meant."""
        with pytest.raises(PolicyRefused):
            await bucket.put("a.txt", chunks(b"x"), user=ANON)

    async def test_a_read_only_bucket_refuses_every_write(self):
        held = Bucket("exports", MemoryDriver(), policy=ReadOnly())

        with pytest.raises(PolicyRefused):
            await held.put("a.txt", chunks(b"x"), user=User())

    async def test_a_read_only_bucket_refuses_a_signed_write(self):
        held = Bucket("exports", MemoryDriver(), policy=ReadOnly())

        with pytest.raises(PolicyRefused):
            await held.put("a.txt", chunks(b"x"), signed=True)


class TestOwned:
    """The rule most applications actually want, and no visibility flag can
    state."""

    @pytest.fixture
    def avatars(self):
        return Bucket("avatars", MemoryDriver(), policy=Owned())

    async def test_a_user_may_write_under_their_own_prefix(self, avatars):
        await avatars.put("114/face.png", chunks(b"x"), user=User("114"))
        assert await avatars.exists("114/face.png", user=User("114"))

    async def test_a_user_may_not_write_under_another(self, avatars):
        with pytest.raises(PolicyRefused):
            await avatars.put("999/face.png", chunks(b"x"), user=User("114"))

    async def test_a_user_may_not_read_another(self, avatars):
        await avatars.put("999/face.png", chunks(b"x"), user=User("999"))

        with pytest.raises(PolicyRefused):
            await collect(avatars.get("999/face.png", user=User("114")))

    async def test_an_anonymous_caller_gets_nothing(self, avatars):
        with pytest.raises(PolicyRefused):
            await avatars.put("114/face.png", chunks(b"x"), user=ANON)

    async def test_reads_can_be_opened_without_opening_writes(self):
        avatars = Bucket("avatars", MemoryDriver(), policy=Owned(readable=True))
        await avatars.put("999/face.png", chunks(b"x"), user=User("999"))

        assert await collect(avatars.get("999/face.png", user=User("114"))) == b"x"

        with pytest.raises(PolicyRefused):
            await avatars.put("999/face.png", chunks(b"y"), user=User("114"))


class TestSniffingThroughTheBucket:
    async def test_the_stored_type_is_the_sniffed_one(self, bucket):
        await bucket.put(
            "a.png", chunks(b"<!DOCTYPE html><script>"), content_type="image/png",
            signed=True,
        )
        assert (await bucket.stat("a.png", signed=True)).content_type == "text/html"

    async def test_the_declaration_is_kept_for_comparison(self, bucket):
        await bucket.put(
            "a.png", chunks(b"<!DOCTYPE html>"), content_type="image/png", signed=True
        )
        info = await bucket.stat("a.png", signed=True)

        assert info.declared_type == "image/png"
        assert info.mistyped is True

    async def test_an_honest_upload_is_not_flagged(self, bucket):
        await bucket.put(
            "a.png", chunks(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32),
            content_type="image/png", signed=True,
        )
        assert (await bucket.stat("a.png", signed=True)).mistyped is False

    async def test_a_bucket_can_refuse_a_type(self):
        """Stated as what the sniffer decided, so declaring image/png and
        uploading HTML is refused here rather than stored."""
        images = Bucket(
            "avatars", MemoryDriver(), policy=Public(),
            accepts=("image/png", "image/jpeg"),
        )

        with pytest.raises(StorageError, match="does not accept"):
            await images.put(
                "a.png", chunks(b"<!DOCTYPE html>"), content_type="image/png",
                signed=True,
            )

    async def test_a_bucket_accepts_what_it_said_it_would(self):
        images = Bucket(
            "avatars", MemoryDriver(), policy=Public(), accepts=("image/png",)
        )
        stored = await images.put(
            "a.png", chunks(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32), signed=True
        )
        assert stored.content_type == "image/png"


class TestLimits:
    async def test_an_oversized_object_is_refused(self):
        small = Bucket("small", MemoryDriver(), policy=Public(), max_bytes=100)

        with pytest.raises(StorageError, match="exceeds"):
            await small.put("big.bin", chunks(b"x" * 500), signed=True)

    async def test_the_limit_is_enforced_while_streaming(self):
        """Not against a declared Content-Length, which is a number the
        uploader chose. A body that claims one kilobyte and sends five is
        refused at the kilobyte, having buffered none of the rest."""
        small = Bucket("small", MemoryDriver(), policy=Public(), max_bytes=1024)
        sent = 0

        async def endless():
            nonlocal sent
            while True:
                sent += 512
                yield b"x" * 512

        with pytest.raises(StorageError):
            await small.put("big.bin", endless(), signed=True)

        # The probe is capped by the bucket's own limit, so a kilobyte ceiling
        # reads about a kilobyte and not the full four-kilobyte probe.
        assert sent <= 2048

    async def test_something_within_the_limit_is_stored(self):
        small = Bucket("small", MemoryDriver(), policy=Public(), max_bytes=100)
        assert (await small.put("a.bin", chunks(b"x" * 50), signed=True)).size == 50


class TestKeysThroughTheBucket:
    async def test_an_unsafe_key_never_reaches_the_driver(self, bucket):
        with pytest.raises(UnsafeKey):
            await bucket.put("../escape.txt", chunks(b"x"), signed=True)

    async def test_keys_are_normalised_before_anything_else(self, bucket):
        await bucket.put("./a//b.txt", chunks(b"x"), signed=True)
        assert (await bucket.stat("a/b.txt", signed=True)).key == "a/b.txt"


class TestEvents:
    async def test_a_write_is_reported(self, bucket):
        heard = []
        bucket.driver.listen(heard.append)

        await bucket.put("a.txt", chunks(b"hello"), signed=True)

        assert [(e.action, e.key, e.size) for e in heard] == [
            (Action.WRITE, "a.txt", 5)
        ]

    async def test_a_read_is_reported_with_what_was_sent(self, bucket):
        await bucket.put("a.txt", chunks(b"hello"), signed=True)

        heard = []
        bucket.driver.listen(heard.append)
        await collect(bucket.get("a.txt", signed=True))

        assert heard[0].action is Action.READ and heard[0].size == 5

    async def test_deleting_something_absent_is_reported_as_missing(self, bucket):
        heard = []
        bucket.driver.listen(heard.append)

        await bucket.delete("nope.txt", signed=True)

        assert heard[0].outcome == "missing"

    async def test_a_refused_write_is_reported_as_an_error(self):
        small = Bucket("small", MemoryDriver(), policy=Public(), max_bytes=10)
        heard = []
        small.driver.listen(heard.append)

        with pytest.raises(StorageError):
            await small.put("a.png", chunks(b"<!DOCTYPE html>" * 40), signed=True)

        assert heard and heard[0].outcome == "error"

    async def test_an_event_carries_a_duration(self, bucket):
        heard = []
        bucket.driver.listen(heard.append)
        await bucket.put("a.txt", chunks(b"x"), signed=True)

        assert heard[0].duration_ms >= 0


class TestStreaming:
    """The one property a normal test cannot check: everything passes whether
    or not the file was buffered whole."""

    def test_a_large_upload_does_not_grow_memory(self, tmp_path):
        from sillo.storage import LocalDriver

        megabyte = b"x" * (1024 * 1024)

        async def source():
            for _ in range(64):
                yield megabyte

        async def upload():
            held = Bucket("big", LocalDriver(tmp_path), policy=Public())
            await held.put("big.bin", source(), signed=True)

        tracemalloc.start()
        try:
            anyio.run(upload)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        # 64 MB in, and the peak must stay near the probe buffer rather than
        # near the payload.
        assert peak < 8 * 1024 * 1024, f"peaked at {peak / 1e6:.1f} MB"

    async def test_the_stream_is_consumed_once(self, bucket):
        """Catches the accidental `data = b"".join(stream)` somebody adds in
        six months to make an edge case easier."""
        reads = 0

        async def counted():
            nonlocal reads
            for _ in range(4):
                reads += 1
                yield b"x" * 8

        await bucket.put("a.bin", counted(), signed=True)
        assert reads == 4
