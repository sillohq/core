"""
Serving what was stored.

This is the half of content-type sniffing that makes sniffing a defence: the
sniffed type only matters if the browser is told not to reach its own
conclusion. So the assertions here are as much about the headers as about the
bytes.

It is also the first place the route is exercised at all. Everything above it
was unit-tested; a route that is never called is a route whose signature nobody
checked.
"""

from __future__ import annotations

import pytest
from sillo import SilloApp
from sillo.testclient import TestClient

from sillo.storage import (
    BucketConfig,
    Owned,
    Private,
    Public,
    StorageConfig,
    setup_storage,
)
from sillo.storage.base import chunks

SECRET = "an-application-secret-long-enough"

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def app(tmp_path):
    application = SilloApp(title="Serving")
    application.state["secret_key"] = SECRET

    setup_storage(
        application,
        StorageConfig(
            default="public",
            buckets={
                "public": BucketConfig(
                    driver="local", root=str(tmp_path / "public"), policy=Public()
                ),
                "secret": BucketConfig(
                    driver="local", root=str(tmp_path / "secret"), policy=Private()
                ),
                "avatars": BucketConfig(
                    driver="local", root=str(tmp_path / "avatars"), policy=Owned()
                ),
            },
        ),
    )
    return application


async def store(app, bucket: str, key: str, body: bytes, content_type: str = ""):
    """Put an object there, bypassing the policy the way a worker would."""
    await app.state["storage"].bucket(bucket).put(
        key, chunks(body), content_type=content_type, signed=True
    )


class TestServing:
    async def test_a_public_object_is_served(self, app):
        await store(app, "public", "notes/a.txt", b"hello", "text/plain")

        with TestClient(app) as client:
            response = client.get("/storage/public/notes/a.txt")

        assert response.status_code == 200
        assert response.content == b"hello"

    async def test_the_content_type_is_the_sniffed_one(self, app):
        """Not the one the uploader declared."""
        await store(app, "public", "a.png", b"<!DOCTYPE html><b>hi</b>", "image/png")

        with TestClient(app) as client:
            response = client.get("/storage/public/a.png")

        assert response.headers["content-type"].startswith("text/html")

    async def test_a_missing_object_is_404(self, app):
        with TestClient(app) as client:
            assert client.get("/storage/public/nope.txt").status_code == 404

    async def test_an_unknown_bucket_is_404(self, app):
        with TestClient(app) as client:
            assert client.get("/storage/nope/a.txt").status_code == 404

    async def test_a_nested_key_is_served(self, app):
        await store(app, "public", "a/b/c/deep.txt", b"deep", "text/plain")

        with TestClient(app) as client:
            assert client.get("/storage/public/a/b/c/deep.txt").content == b"deep"

    async def test_a_traversing_key_is_404_rather_than_a_file(self, app):
        with TestClient(app) as client:
            response = client.get("/storage/public/../../etc/passwd")

        assert response.status_code == 404


class TestGuards:
    """Sniffing without these headers is half a defence: the browser will
    re-sniff and reach its own conclusion."""

    @pytest.fixture
    async def response(self, app):
        await store(app, "public", "a.png", PNG, "image/png")

        with TestClient(app) as client:
            return client.get("/storage/public/a.png")

    def test_the_browser_is_told_not_to_sniff(self):
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_it_is_sandboxed(self):
        assert "sandbox" in response.headers["content-security-policy"]

    def test_it_carries_no_referrer(self):
        assert response.headers["referrer-policy"] == "no-referrer"

    def test_it_is_not_cross_origin_readable(self):
        assert response.headers["cross-origin-resource-policy"] == "same-origin"

    def test_a_render_safe_type_is_shown_inline(self):
        assert response.headers["content-disposition"].startswith("inline")

    async def test_anything_else_is_downloaded(self, app):
        """An unexpected type must not execute in this origin."""
        await store(app, "public", "a.bin", b"\xde\xad\xbe\xef" * 8)

        with TestClient(app) as client:
            response = client.get("/storage/public/a.bin")

        assert response.headers["content-disposition"].startswith("attachment")

    async def test_html_is_downloaded_however_it_was_named(self, app):
        await store(app, "public", "a.png", b"<!DOCTYPE html><script>", "image/png")

        with TestClient(app) as client:
            response = client.get("/storage/public/a.png")

        assert response.headers["content-disposition"].startswith("attachment")

    async def test_a_filename_cannot_inject_a_header(self, app):
        """The filename came from whoever uploaded the file."""
        await store(app, "public", 'a"; x=y.txt', b"x", "text/plain")

        with TestClient(app) as client:
            response = client.get('/storage/public/a"; x=y.txt')

        assert '"' not in response.headers["content-disposition"].split("filename=")[1][1:-1]

    def test_it_carries_an_etag(self):
        assert response.headers["etag"].startswith('"')


class TestPrivacy:
    async def test_a_private_object_is_not_served(self, app):
        await store(app, "secret", "a.txt", b"classified", "text/plain")

        with TestClient(app) as client:
            response = client.get("/storage/secret/a.txt")

        assert response.status_code == 404
        assert b"classified" not in response.content

    async def test_a_refusal_looks_like_an_absence(self, app):
        """A 403 on a private bucket confirms the object exists, which is half
        of what somebody probing for it wants to know."""
        await store(app, "secret", "here.txt", b"x", "text/plain")

        with TestClient(app) as client:
            present = client.get("/storage/secret/here.txt")
            absent = client.get("/storage/secret/gone.txt")

        assert present.status_code == absent.status_code == 404
        assert present.json() == absent.json()

    async def test_a_signature_opens_it(self, app):
        await store(app, "secret", "a.txt", b"classified", "text/plain")
        url = app.state["storage"].bucket("secret").signed_url("a.txt")

        with TestClient(app) as client:
            response = client.get(url)

        assert response.status_code == 200
        assert response.content == b"classified"

    async def test_a_tampered_signature_does_not(self, app):
        await store(app, "secret", "a.txt", b"classified", "text/plain")
        url = app.state["storage"].bucket("secret").signed_url("a.txt")

        with TestClient(app) as client:
            response = client.get(url[:-4] + "AAAA")

        assert response.status_code == 404

    async def test_a_signature_for_one_object_does_not_open_another(self, app):
        await store(app, "secret", "a.txt", b"a", "text/plain")
        await store(app, "secret", "b.txt", b"b", "text/plain")

        token = app.state["storage"].bucket("secret").signed_url("a.txt").split("token=")[1]

        with TestClient(app) as client:
            response = client.get(f"/storage/secret/b.txt?token={token}")

        assert response.status_code == 404

    async def test_an_expired_signature_does_not(self, app):
        await store(app, "secret", "a.txt", b"classified", "text/plain")
        url = app.state["storage"].bucket("secret").signed_url("a.txt", expires_in=-1)

        with TestClient(app) as client:
            assert client.get(url).status_code == 404

    async def test_an_owned_object_is_not_served_to_a_stranger(self, app):
        await store(app, "avatars", "114/face.png", PNG, "image/png")

        with TestClient(app) as client:
            assert client.get("/storage/avatars/114/face.png").status_code == 404
