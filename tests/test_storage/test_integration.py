"""
Storage inside a real application.

The wiring is where the assumptions are: that `app.state` holds what the rest of
the framework expects, that the lifecycle hooks fire, that the serving route
mounts where it says. A mock application would agree with every one of those and
prove none of them.
"""

from __future__ import annotations

import pytest
from sillo import SilloApp

from sillo.storage import (
    BucketConfig,
    MemoryDriver,
    Owned,
    Public,
    StorageConfig,
    setup_storage,
)
from sillo.storage.base import chunks, collect


SECRET = "an-application-secret-long-enough"


@pytest.fixture
def app(tmp_path):
    application = SilloApp(title="Storage test")
    application.state["secret_key"] = SECRET

    setup_storage(
        application,
        StorageConfig(
            default="attachments",
            buckets={
                "attachments": BucketConfig(
                    driver="local", root=str(tmp_path / "attachments"), policy=Public()
                ),
                "avatars": BucketConfig(
                    driver="local",
                    root=str(tmp_path / "avatars"),
                    policy=Owned(),
                    accepts=("image/png",),
                ),
                "scratch": BucketConfig(driver="memory", policy=Public()),
            },
        ),
    )
    return application


class TestWiring:
    def test_it_lands_on_the_application_state(self, app):
        assert "storage" in app.state

    def test_calling_it_twice_returns_the_same_storage(self, app):
        assert setup_storage(app, StorageConfig()) is app.state["storage"]

    def test_the_default_bucket_needs_no_name(self, app):
        assert app.state["storage"].bucket().name == "attachments"

    def test_an_unknown_bucket_is_a_clear_error(self, app):
        with pytest.raises(KeyError, match="Configured"):
            app.state["storage"].bucket("nope")

    def test_each_bucket_gets_the_driver_it_asked_for(self, app):
        storage = app.state["storage"]
        assert storage.bucket("scratch").driver.name == "memory"
        assert storage.bucket("attachments").driver.name == "local"

    def test_the_serving_route_is_mounted(self, app):
        paths = {getattr(route, "raw_path", "") for route in app.get_all_routes()}
        assert any(path.startswith("/storage/") for path in paths)

    def test_a_bucket_with_no_root_is_refused_at_startup(self):
        """Rather than at the first upload, in production, on a Friday."""
        with pytest.raises(ValueError, match="no root"):
            setup_storage(
                SilloApp(title="broken"),
                StorageConfig(buckets={"x": BucketConfig(driver="local")}),
            )

    def test_asking_for_s3_without_the_extra_says_so(self):
        with pytest.raises(ValueError, match="storage-s3"):
            setup_storage(
                SilloApp(title="broken"),
                StorageConfig(buckets={"x": BucketConfig(driver="s3", bucket="b")}),
            )

    def test_an_unknown_driver_lists_the_known_ones(self):
        with pytest.raises(ValueError, match="memory, local, s3"):
            setup_storage(
                SilloApp(title="broken"),
                StorageConfig(buckets={"x": BucketConfig(driver="ftp")}),
            )


class TestSignedUrls:
    def test_a_bucket_can_mint_one(self, app):
        url = app.state["storage"].bucket("attachments").signed_url("a.txt")
        assert "/storage/attachments/a.txt?token=" in url

    def test_the_secret_comes_from_the_application(self, app):
        """A bucket with no signer would raise instead."""
        assert app.state["storage"].bucket("scratch") is not None
        app.state["storage"].bucket("attachments").signed_url("a.txt")

    def test_the_url_is_bound_to_the_object(self, app):
        bucket = app.state["storage"].bucket("attachments")
        first = bucket.signed_url("a.txt")
        second = bucket.signed_url("b.txt")

        assert first.split("token=")[1] != second.split("token=")[1]

    def test_a_write_url_carries_the_buckets_own_ceiling(self, tmp_path):
        application = SilloApp(title="limited")
        application.state["secret_key"] = SECRET
        setup_storage(
            application,
            StorageConfig(
                default="small",
                buckets={
                    "small": BucketConfig(
                        driver="local",
                        root=str(tmp_path / "small"),
                        policy=Public(),
                        max_bytes=1024,
                    )
                },
            ),
        )

        bucket = application.state["storage"].bucket()
        url = bucket.signed_url("a.bin", method="PUT")
        token = url.split("token=")[1]

        grant = bucket.driver._signer.verify(token, key="a.bin", method="PUT")
        assert grant.max_bytes == 1024


class TestThroughTheApplication:
    async def test_a_round_trip(self, app):
        bucket = app.state["storage"].bucket("scratch")

        await bucket.put("notes/a.txt", chunks(b"hello"), signed=True)
        assert await collect(bucket.get("notes/a.txt", user=None)) == b"hello"

    async def test_the_avatars_bucket_enforces_its_own_rules(self, app):
        from sillo.storage.errors import PolicyRefused, StorageError

        bucket = app.state["storage"].bucket("avatars")

        class User:
            is_authenticated = True
            identity = "114"

        # Right prefix, right type.
        await bucket.put(
            "114/face.png",
            chunks(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32),
            content_type="image/png",
            user=User(),
        )

        # Right prefix, wrong content whatever it claims.
        with pytest.raises(StorageError):
            await bucket.put(
                "114/evil.png",
                chunks(b"<!DOCTYPE html><script>"),
                content_type="image/png",
                user=User(),
            )

        # Wrong prefix.
        with pytest.raises(PolicyRefused):
            await bucket.put("999/face.png", chunks(b"x"), user=User())

    async def test_one_listener_sees_every_bucket(self, app):
        heard = []
        app.state["storage"].listen(heard.append)

        await app.state["storage"].bucket("scratch").put(
            "a.txt", chunks(b"x"), signed=True
        )

        assert [event.bucket for event in heard] == ["scratch"]

    async def test_shutting_down_releases_the_drivers(self, app):
        storage = app.state["storage"]
        await storage.bucket("scratch").put("a.txt", chunks(b"x"), signed=True)
        await storage.close()

        assert (await storage.bucket("scratch").driver.page()).files == ()


class TestFake:
    """The memory driver is what a test double should be: held to exactly the
    contract production is, rather than a local disk wearing a hat."""

    async def test_it_pages_like_the_real_thing(self):
        driver = MemoryDriver()
        for index in range(10):
            await driver.write(f"a/{index:02d}.txt", chunks(b"x"))

        page = await driver.page("a/", limit=3)
        assert len(page.files) == 3 and page.more is True
