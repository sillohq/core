"""
sillo.storage.config — what a project declares.

One dataclass, not a pile of keyword arguments.  ``setup_record`` takes a
``DatabaseConfig`` and can grow an option without breaking a signature;
``setup_work`` takes keywords and cannot. This follows the first.
"""

from __future__ import annotations

import dataclasses
from typing import Any

__all__ = ["BucketConfig", "StorageConfig"]


@dataclasses.dataclass(frozen=True, slots=True)
class BucketConfig:
    """One bucket.

    Attributes:
        driver: ``memory``, ``local`` or ``s3``.
        policy: Who may do what. Defaults to ``Private()`` — a bucket nobody
            configured should not be readable because nobody configured it.
        root: The directory, for the local driver.
        bucket: The remote bucket name, for S3.
        endpoint: The S3 endpoint, for anything that is not AWS.
        region: The S3 region.
        access_key: The S3 access key. Read from the environment in practice.
        secret_key: The S3 secret key.
        max_bytes: Largest object this bucket accepts. Zero for no limit.
        accepts: Content types this bucket accepts, after sniffing. Empty for
            anything. Stated as what the *sniffer* decided, so declaring
            ``image/png`` and uploading HTML is refused here rather than
            stored.
    """

    driver: str = "local"
    policy: Any = None
    root: str = ""
    bucket: str = ""
    endpoint: str = ""
    region: str = "us-east-1"
    access_key: str = ""
    secret_key: str = ""
    max_bytes: int = 0
    accepts: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True, slots=True)
class StorageConfig:
    """Every bucket, and what they share.

    Attributes:
        buckets: Bucket names to their configuration.
        default: Which bucket ``storage.bucket()`` returns unasked.
        secret: What signs URLs. Falls back to the application's own secret.
        route: Where the serving route is mounted. Every signed URL points
            under this.
        serve: Mount the serving route at all. Off means signed URLs can still
            be minted for S3, which serves them itself, and local ones have
            nowhere to point.
    """

    buckets: dict[str, BucketConfig] = dataclasses.field(default_factory=dict)
    default: str = ""
    secret: str = ""
    route: str = "/storage"
    serve: bool = True

    def bucket(self, name: str = "") -> BucketConfig:
        """One bucket's configuration.

        Args:
            name: The bucket's name, or empty for the default.

        Returns:
            Its configuration.

        Raises:
            KeyError: If no such bucket was declared. Naming a bucket that does
                not exist is a typo, and creating one silently is how a project
                ends up writing to somewhere nothing reads.
        """
        wanted = name or self.default

        if not wanted:
            raise KeyError("no bucket named, and no default configured")

        if wanted not in self.buckets:
            known = ", ".join(sorted(self.buckets)) or "none"
            raise KeyError(f"no bucket {wanted!r}. Configured: {known}")

        return self.buckets[wanted]
