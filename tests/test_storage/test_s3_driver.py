"""Tests for S3Driver against DriverContract and S3-specific behaviors."""

from __future__ import annotations

import datetime as dt
import hashlib
from urllib.parse import unquote
from xml.sax.saxutils import escape

import httpx
import pytest

from sillo.storage.base import chunks, collect
from sillo.storage.drivers.s3 import S3Driver
from sillo.storage.errors import StorageError

from .contract import DriverContract


class MockS3Handler:
    """In-memory S3 REST API simulator for testing S3Driver."""

    def __init__(self, bucket: str = "test-bucket") -> None:
        self.bucket = bucket
        self.objects: dict[str, dict] = {}
        self.bucket_exists = True

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path).lstrip("/")
        parts = path.split("/", 1)
        bucket = parts[0] if parts else ""
        key = parts[1] if len(parts) > 1 else ""

        # Bucket operations
        if not key:
            if request.method == "HEAD":
                if not self.bucket_exists or bucket != self.bucket:
                    return httpx.Response(404)
                return httpx.Response(200)

            if request.method == "PUT":
                self.bucket = bucket
                self.bucket_exists = True
                return httpx.Response(200)

            if request.method == "GET":
                if not self.bucket_exists or bucket != self.bucket:
                    return httpx.Response(404)

                prefix = request.url.params.get("prefix", "")
                delimiter = request.url.params.get("delimiter", "")
                max_keys = int(request.url.params.get("max-keys", "1000"))
                token = request.url.params.get("continuation-token", "")

                matching_keys = sorted(k for k in self.objects if k.startswith(prefix))
                if token:
                    matching_keys = [k for k in matching_keys if k > token]

                entries = []
                common_prefixes = set()
                for k in matching_keys:
                    rest = k[len(prefix) :]
                    if delimiter and delimiter in rest:
                        slash_idx = rest.index(delimiter) + len(delimiter)
                        common_prefixes.add(prefix + rest[:slash_idx])
                    else:
                        entries.append(k)

                paged = entries[:max_keys]
                truncated = len(entries) > max_keys
                next_token = paged[-1] if truncated and paged else ""

                xml_parts = [
                    '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">',
                    f"<Name>{escape(bucket)}</Name>",
                    f"<Prefix>{escape(prefix)}</Prefix>",
                    f"<MaxKeys>{max_keys}</MaxKeys>",
                    f"<IsTruncated>{'true' if truncated else 'false'}</IsTruncated>",
                ]
                if next_token:
                    xml_parts.append(
                        f"<NextContinuationToken>{escape(next_token)}</NextContinuationToken>"
                    )
                for k in paged:
                    item = self.objects[k]
                    mod_str = item["modified"].strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    xml_parts.append(
                        f"<Contents><Key>{escape(k)}</Key>"
                        f"<LastModified>{mod_str}</LastModified>"
                        f"<ETag>\"{item['etag']}\"</ETag>"
                        f"<Size>{len(item['body'])}</Size></Contents>"
                    )
                for cp in sorted(common_prefixes):
                    xml_parts.append(
                        f"<CommonPrefixes><Prefix>{escape(cp)}</Prefix></CommonPrefixes>"
                    )
                xml_parts.append("</ListBucketResult>")
                return httpx.Response(
                    200,
                    content="".join(xml_parts).encode("utf-8"),
                    headers={"content-type": "application/xml"},
                )

        # Object operations
        if not self.bucket_exists or bucket != self.bucket:
            return httpx.Response(
                404,
                text="<Error><Code>NoSuchBucket</Code></Error>",
                headers={"content-type": "application/xml"},
            )

        if request.method == "PUT":
            body = request.read()
            etag = hashlib.md5(body).hexdigest()
            content_type = request.headers.get("content-type", "application/octet-stream")
            declared_type = request.headers.get("x-amz-meta-declared-type", "")
            self.objects[key] = {
                "body": body,
                "content_type": content_type,
                "declared_type": declared_type,
                "etag": etag,
                "modified": dt.datetime.now(dt.timezone.utc),
            }
            return httpx.Response(200, headers={"etag": f'"{etag}"'})

        if request.method == "HEAD":
            if key not in self.objects:
                return httpx.Response(404)
            item = self.objects[key]
            headers = {
                "content-length": str(len(item["body"])),
                "content-type": item["content_type"],
                "etag": f'"{item["etag"]}"',
                "last-modified": item["modified"].strftime("%a, %d %b %Y %H:%M:%S GMT"),
            }
            if item["declared_type"]:
                headers["x-amz-meta-declared-type"] = item["declared_type"]
            return httpx.Response(200, headers=headers)

        if request.method == "GET":
            if key not in self.objects:
                return httpx.Response(404)
            item = self.objects[key]
            body = item["body"]
            range_header = request.headers.get("range")
            if range_header and range_header.startswith("bytes="):
                rng = range_header[6:].split("-")
                start = int(rng[0])
                end = int(rng[1])
                body = body[start : end + 1]
                return httpx.Response(
                    206,
                    content=body,
                    headers={
                        "content-range": f"bytes {start}-{end}/{len(item['body'])}",
                        "content-type": item["content_type"],
                    },
                )
            return httpx.Response(
                200,
                content=body,
                headers={
                    "content-type": item["content_type"],
                    "content-length": str(len(body)),
                    "etag": f'"{item["etag"]}"',
                },
            )

        if request.method == "DELETE":
            self.objects.pop(key, None)
            return httpx.Response(204)

        return httpx.Response(405)


class TestS3DriverContract(DriverContract):
    """S3Driver must satisfy the same contract local and memory do."""

    @pytest.fixture
    async def driver(self):
        handler = MockS3Handler("contract-bucket")
        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        built = S3Driver(
            bucket="contract-bucket",
            endpoint="http://s3.local:9000",
            access_key="test-key",
            secret_key="test-secret",
            client=client,
        )
        yield built
        await built.close()
        await client.aclose()


# ── S3-specific unit tests ───────────────────────────────────────────────


async def test_s3_driver_repr():
    driver = S3Driver(bucket="my-bucket")
    assert repr(driver) == "S3Driver(name='s3')"
    await driver.close()


def test_s3_driver_requires_bucket():
    with pytest.raises(ValueError, match="needs a bucket"):
        S3Driver(bucket="")


async def test_ensure_bucket_existing():
    handler = MockS3Handler("existing-bucket")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        driver = S3Driver(bucket="existing-bucket", client=client)
        assert await driver.ensure_bucket() is False


async def test_ensure_bucket_missing():
    handler = MockS3Handler("to-create")
    handler.bucket_exists = False
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        driver = S3Driver(bucket="to-create", client=client)
        assert await driver.ensure_bucket() is True
        assert handler.bucket_exists is True


async def test_ensure_bucket_permission_error():
    def reject_handler(request):
        return httpx.Response(403)

    transport = httpx.MockTransport(reject_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        driver = S3Driver(bucket="locked", client=client)
        with pytest.raises(StorageError, match="check the access key and secret"):
            await driver.ensure_bucket()


async def test_first_write_creates_bucket_when_missing():
    handler = MockS3Handler("fresh-bucket")
    handler.bucket_exists = False
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        driver = S3Driver(bucket="fresh-bucket", client=client)
        stored = await driver.write("test.txt", chunks(b"hello"))
        assert stored.size == 5
        assert handler.bucket_exists is True


async def test_read_range():
    handler = MockS3Handler("media-bucket")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        driver = S3Driver(bucket="media-bucket", client=client)
        await driver.write("video.mp4", chunks(b"0123456789"))
        slice_data = await collect(driver.read_range("video.mp4", 3, 7))
        assert slice_data == b"34567"


def test_signed_url_generation():
    driver = S3Driver(
        bucket="photos",
        endpoint="https://s3.amazonaws.com",
        access_key="AKIA123",
        secret_key="SECRET123",
        region="eu-central-1",
        public_endpoint="https://cdn.example.com",
    )
    url = driver.signed_url("user/avatar.png", expires_in=600)
    assert url.startswith("https://cdn.example.com/photos/user/avatar.png?")
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in url
    assert "X-Amz-Credential=AKIA123" in url
    assert "eu-central-1" in url
    assert "X-Amz-Expires=600" in url
    assert "X-Amz-Signature=" in url

    put_url = driver.signed_url(
        "user/upload.png", method="PUT", content_type="image/png"
    )
    assert "X-Amz-SignedHeaders=content-type%3Bhost" in put_url


async def test_s3_capabilities():
    driver = S3Driver(bucket="cap-bucket")
    caps = await driver.capabilities()
    assert caps["driver"] == "s3"
    assert caps["signed_urls"] is True
    assert caps["server_side_copy"] is False
    await driver.close()


def test_url_virtual_hosted_style():
    driver = S3Driver(
        bucket="mybucket",
        endpoint="https://s3.eu-west-1.amazonaws.com",
        path_style=False,
    )
    url, path = driver._url("photo.jpg")
    assert url == "https://mybucket.s3.eu-west-1.amazonaws.com/photo.jpg"
    assert path == "/photo.jpg"
