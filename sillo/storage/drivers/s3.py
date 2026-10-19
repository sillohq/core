"""
sillo.storage.drivers.s3 — objects in an S3-compatible bucket.

Ships with the ``sillo[storage-s3]`` extra. Works with AWS S3, MinIO,
Cloudflare R2, Backblaze B2, DigitalOcean Spaces, Wasabi and Ceph.

Requests are signed with AWS Signature Version 4 (HMAC-SHA256) using httpx
rather than pulling in boto3.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote, urlencode, urlparse

try:
    import httpx
except ImportError as err:  # pragma: no cover
    raise ImportError(
        "the s3 driver requires httpx: install sillo-framework[storage-s3]"
    ) from err

from ..base import Driver, FileInfo, Page, Stored
from ..errors import FileNotFound, StorageError

__all__ = ["S3Driver"]

CHUNK = 64 * 1024
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
DEFAULT_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


class S3Driver(Driver):
    """Objects in an S3-compatible bucket.

    Args:
        bucket: The remote bucket name.
        endpoint: The service URL (empty for AWS: ``https://s3.<region>.amazonaws.com``).
        region: The signing region.
        access_key, secret_key: Credentials.
        prefix: A key prefix, so several buckets can share one remote bucket.
        path_style: Address the bucket in the path (MinIO, Ceph) instead of the host.
        public_endpoint: The origin browsers reach the service at, used only for
            presigned URLs. Set it when ``endpoint`` is an internal address (e.g. a
            ``minio`` container) that a client outside the network cannot resolve.
        timeout: HTTP request timeout in seconds.
        client: Optional custom ``httpx.AsyncClient`` (useful for tests or custom transports).
    """

    name = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        endpoint: str = "",
        region: str = "us-east-1",
        access_key: str = "",
        secret_key: str = "",
        prefix: str = "",
        path_style: bool = True,
        public_endpoint: str = "",
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__()
        if not bucket:
            raise ValueError("the s3 driver needs a bucket")
        self.bucket = bucket
        self.region = region or "us-east-1"
        self.endpoint = (endpoint or f"https://s3.{self.region}.amazonaws.com").rstrip("/")
        self.access_key = access_key
        self.secret_key = secret_key
        self.prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        self.path_style = path_style
        self.public_endpoint = public_endpoint.rstrip("/")
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(timeout=timeout)
            self._owns_client = True

    # ── addressing and signing ───────────────────────────────────────────

    def _url(self, key: str = "", *, public: bool = False) -> tuple[str, str]:
        parsed = urlparse((public and self.public_endpoint) or self.endpoint)
        object_path = quote(self.prefix + key, safe="/~") if key else ""
        if self.path_style:
            host = parsed.netloc
            path = f"/{self.bucket}/{object_path}" if key else f"/{self.bucket}"
        else:
            host = f"{self.bucket}.{parsed.netloc}"
            path = f"/{object_path}" if object_path else "/"
        return f"{parsed.scheme}://{host}{path}", path

    def _signing_key(self, day: str) -> bytes:
        key = _sign(f"AWS4{self.secret_key}".encode(), day)
        key = _sign(key, self.region)
        key = _sign(key, "s3")
        return _sign(key, "aws4_request")

    def _headers(
        self,
        method: str,
        url: str,
        path: str,
        query: dict[str, str] | None = None,
        *,
        payload_hash: str = EMPTY_SHA256,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        now = dt.datetime.now(dt.UTC)
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        day = now.strftime("%Y%m%d")
        host = urlparse(url).netloc
        headers = {
            "host": host,
            "x-amz-date": stamp,
            "x-amz-content-sha256": payload_hash,
            **{k.lower(): v for k, v in (extra or {}).items()},
        }
        signed = ";".join(sorted(headers))
        canonical_headers = "".join(f"{name}:{headers[name].strip()}\n" for name in sorted(headers))
        canonical_query = urlencode(sorted((query or {}).items()), quote_via=quote, safe="~")
        canonical = (
            f"{method}\n"
            f"{path}\n"
            f"{canonical_query}\n"
            f"{canonical_headers}\n"
            f"{signed}\n"
            f"{payload_hash}"
        )
        scope = f"{day}/{self.region}/s3/aws4_request"
        to_sign = (
            f"AWS4-HMAC-SHA256\n"
            f"{stamp}\n"
            f"{scope}\n"
            f"{hashlib.sha256(canonical.encode()).hexdigest()}"
        )
        signature = hmac.new(self._signing_key(day), to_sign.encode(), hashlib.sha256).hexdigest()
        headers["authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, SignedHeaders={signed}, Signature={signature}"
        )
        headers.pop("host")
        return headers

    async def _request(
        self,
        method: str,
        key: str = "",
        *,
        query: dict[str, str] | None = None,
        content: Any = None,
        payload_hash: str = EMPTY_SHA256,
        extra: dict[str, str] | None = None,
    ) -> httpx.Response:
        url, path = self._url(key)
        headers = self._headers(method, url, path, query, payload_hash=payload_hash, extra=extra)
        return await self._client.request(
            method, url, params=query, content=content, headers=headers
        )

    # ── the contract ─────────────────────────────────────────────────────

    async def ensure_bucket(self) -> bool:
        """Create the remote bucket when it does not exist.

        Idempotent: an existing bucket (``200`` on ``HEAD``, or ``409`` on
        ``PUT``) is left alone. That is what lets a fresh MinIO work with no
        setup step.

        Returns:
            ``True`` when this call created the bucket.

        Raises:
            StorageError: The service refused (bad credentials, no permission).
        """
        head = await self._request("HEAD")
        if head.status_code < 300:
            return False
        if head.status_code in (401, 403):
            raise StorageError(
                f"s3 refused access to bucket {self.bucket!r} ({head.status_code}): check the access key and secret"
            )
        body = (
            ""
            if self.region == "us-east-1"
            else f"<CreateBucketConfiguration><LocationConstraint>{self.region}</LocationConstraint></CreateBucketConfiguration>"
        )
        payload = body.encode()
        response = await self._request(
            "PUT", content=payload, payload_hash=hashlib.sha256(payload).hexdigest()
        )
        if response.status_code in (200, 409):
            return response.status_code == 200
        raise StorageError(
            f"could not create bucket {self.bucket!r} ({response.status_code}): {response.text[:200]}"
        )

    async def write(
        self,
        key: str,
        stream: AsyncIterator[bytes],
        *,
        content_type: str = "",
        declared_type: str = "",
    ) -> Stored:
        digest = hashlib.sha256()
        size = 0
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as spool:
            async for chunk in stream:
                digest.update(chunk)
                size += len(chunk)
                spool.write(chunk)
            spool.seek(0)
            resolved = content_type or "application/octet-stream"
            extra = {"content-type": resolved, "content-length": str(size)}
            if declared_type:
                extra["x-amz-meta-declared-type"] = declared_type
            body = spool.read()
            response = await self._request(
                "PUT", key, content=body, payload_hash=digest.hexdigest(), extra=extra
            )
            if response.status_code == 404 and "NoSuchBucket" in response.text:
                await self.ensure_bucket()
                response = await self._request(
                    "PUT", key, content=body, payload_hash=digest.hexdigest(), extra=extra
                )
        if response.status_code >= 300:
            raise StorageError(
                f"s3 refused the write ({response.status_code}): {response.text[:200]}"
            )
        return Stored(key, size, resolved, response.headers.get("etag", "").strip('"'))

    async def read(self, key: str) -> AsyncIterator[bytes]:
        url, path = self._url(key)
        headers = self._headers("GET", url, path)
        async with self._client.stream("GET", url, headers=headers) as response:
            if response.status_code == 404:
                raise FileNotFound(key)
            if response.status_code >= 300:
                raise StorageError(f"s3 refused the read ({response.status_code})")
            async for chunk in response.aiter_bytes(CHUNK):
                yield chunk

    async def read_range(self, key: str, start: int, end: int) -> AsyncIterator[bytes]:
        """Stream bytes ``start``..``end`` (inclusive)."""
        url, path = self._url(key)
        headers = self._headers("GET", url, path, extra={"range": f"bytes={start}-{end}"})
        async with self._client.stream("GET", url, headers=headers) as response:
            if response.status_code == 404:
                raise FileNotFound(key)
            if response.status_code >= 300:
                raise StorageError(f"s3 refused the read ({response.status_code})")
            async for chunk in response.aiter_bytes(CHUNK):
                yield chunk

    async def stat(self, key: str) -> FileInfo:
        response = await self._request("HEAD", key)
        if response.status_code == 404:
            raise FileNotFound(key)
        if response.status_code >= 300:
            raise StorageError(f"s3 refused the stat ({response.status_code})")
        modified = response.headers.get("last-modified")
        timestamp = 0.0
        if modified:
            try:
                timestamp = (
                    dt.datetime.strptime(modified, "%a, %d %b %Y %H:%M:%S %Z")
                    .replace(tzinfo=dt.UTC)
                    .timestamp()
                )
            except ValueError:
                timestamp = 0.0
        return FileInfo(
            key=key,
            size=int(response.headers.get("content-length", 0)),
            content_type=response.headers.get("content-type", "application/octet-stream"),
            modified=timestamp,
            etag=response.headers.get("etag", "").strip('"'),
            declared_type=response.headers.get("x-amz-meta-declared-type", ""),
        )

    async def delete(self, key: str) -> bool:
        if not await self.exists(key):
            return False
        response = await self._request("DELETE", key)
        if response.status_code >= 300 and response.status_code != 404:
            raise StorageError(f"s3 refused the delete ({response.status_code})")
        return True

    async def page(self, prefix: str = "", *, cursor: str = "", limit: int = 100) -> Page:
        query = {
            "list-type": "2",
            "prefix": self.prefix + prefix,
            "max-keys": str(max(1, min(limit, 1000))),
        }
        if cursor:
            query["continuation-token"] = cursor
        response = await self._request("GET", "", query=query)
        if response.status_code >= 300:
            raise StorageError(f"s3 refused the listing ({response.status_code})")
        root = ET.fromstring(response.text)
        ns = DEFAULT_NS
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"
        else:
            ns = ""
        strip = len(self.prefix)
        files = []
        keys = []
        for item in root.findall(f"{ns}Contents"):
            raw_key = item.findtext(f"{ns}Key", "")
            key = raw_key[strip:] if raw_key.startswith(self.prefix) else raw_key
            keys.append(key)
            modified = item.findtext(f"{ns}LastModified", "")
            try:
                timestamp = dt.datetime.fromisoformat(modified.replace("Z", "+00:00")).timestamp()
            except ValueError:
                timestamp = 0.0
            files.append(
                FileInfo(
                    key=key,
                    size=int(item.findtext(f"{ns}Size", "0")),
                    modified=timestamp,
                    etag=item.findtext(f"{ns}ETag", "").strip('"'),
                )
            )
        prefixes_set = {
            p.findtext(f"{ns}Prefix", "")[strip:] for p in root.findall(f"{ns}CommonPrefixes")
        }
        prefixes_set.update(_prefixes(keys, prefix))
        prefixes = tuple(sorted(p for p in prefixes_set if p))
        next_cursor = (
            root.findtext(f"{ns}NextContinuationToken", "")
            if root.findtext(f"{ns}IsTruncated") == "true"
            else ""
        )
        return Page(files=tuple(files), prefixes=prefixes, cursor=next_cursor)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def signed_url(
        self,
        key: str,
        *,
        method: str = "GET",
        expires_in: int = 300,
        content_type: str = "",
        max_bytes: int = 0,
    ) -> str:
        url, path = self._url(key, public=True)
        now = dt.datetime.now(dt.UTC)
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        day = now.strftime("%Y%m%d")
        scope = f"{day}/{self.region}/s3/aws4_request"
        host = urlparse(url).netloc
        signed_headers = "host"
        query = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self.access_key}/{scope}",
            "X-Amz-Date": stamp,
            "X-Amz-Expires": str(max(1, min(expires_in, 604800))),
            "X-Amz-SignedHeaders": signed_headers,
        }
        if content_type and method.upper() == "PUT":
            query["X-Amz-SignedHeaders"] = signed_headers = "content-type;host"
        canonical_query = urlencode(sorted(query.items()), quote_via=quote, safe="~")
        canonical_headers = f"host:{host}\n"
        if signed_headers == "content-type;host":
            canonical_headers = f"content-type:{content_type}\nhost:{host}\n"
        canonical = (
            f"{method.upper()}\n"
            f"{path}\n"
            f"{canonical_query}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"UNSIGNED-PAYLOAD"
        )
        to_sign = (
            f"AWS4-HMAC-SHA256\n"
            f"{stamp}\n"
            f"{scope}\n"
            f"{hashlib.sha256(canonical.encode()).hexdigest()}"
        )
        signature = hmac.new(self._signing_key(day), to_sign.encode(), hashlib.sha256).hexdigest()
        return f"{url}?{canonical_query}&X-Amz-Signature={signature}"

    async def capabilities(self) -> dict[str, object]:
        return {"signed_urls": True, "server_side_copy": False, "driver": "s3"}


def _prefixes(keys: list[str], prefix: str) -> tuple[str, ...]:
    found = set()
    for key in keys:
        rest = key[len(prefix) :]
        head, slash, _ = rest.partition("/")
        if slash:
            found.add(f"{prefix}{head}/")
    return tuple(sorted(found))
