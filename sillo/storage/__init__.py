"""
sillo.storage — buckets over local disk and S3-compatible object storage.

    from sillo.storage import setup_storage, StorageConfig, BucketConfig
    from sillo.storage.policies import Owned, Private

    storage = setup_storage(app, StorageConfig(
        default="attachments",
        buckets={
            "attachments": BucketConfig(driver="local", root="storage/attachments"),
            "avatars": BucketConfig(driver="local", root="storage/avatars",
                                    policy=Owned(), accepts=("image/png", "image/jpeg")),
        },
    ))

    await storage.bucket("avatars").put(f"{user.id}/face.png", upload, user=user)

Five properties this package is built around, each of which forces something:

* **One driver contract** over disk and object storage — so a project can move
  between them without changing a line, and so a third-party backend has
  something to conform to.
* **Streamed uploads that never buffer a whole file** — so ``write`` takes an
  async iterator and there is no convenience that takes bytes.
* **Signed URLs scoped by method, expiry, content type and size** — all four,
  because each one omitted is a permission accidentally granted.
* **Content-type sniffing, because the declared type is not evidence** — the
  sniffer decides what is stored and served; the claim is kept only to be
  compared against it.
* **Per-bucket access rules as policies, not a public flag** — because the rule
  most applications want is "this user, under their own prefix", which two
  values cannot express.
"""

from __future__ import annotations

from .base import Action, Driver, FileInfo, Page, StorageEvent, Stored, chunks, collect
from .bucket import Bucket
from .config import BucketConfig, StorageConfig
from .drivers import LocalDriver, MemoryDriver
from .errors import (
    FileNotFound,
    PolicyRefused,
    SignatureInvalid,
    StorageError,
    UnsafeKey,
)
from .paths import normalise
from .policies import Owned, Private, Public, ReadOnly, Signed
from .signing import SignedGrant, Signer
from .storage import Storage, setup_storage
from .uploads import stream_upload

__all__ = [
    "Action",
    "Bucket",
    "BucketConfig",
    "Driver",
    "FileInfo",
    "FileNotFound",
    "LocalDriver",
    "MemoryDriver",
    "Owned",
    "Page",
    "PolicyRefused",
    "Private",
    "Public",
    "ReadOnly",
    "SignatureInvalid",
    "Signed",
    "SignedGrant",
    "Signer",
    "Storage",
    "StorageConfig",
    "StorageError",
    "StorageEvent",
    "Stored",
    "UnsafeKey",
    "chunks",
    "collect",
    "normalise",
    "setup_storage",
    "stream_upload",
]
