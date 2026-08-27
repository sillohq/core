"""Coverage for StorageConfig.bucket()'s no-name-and-no-default error path."""

from __future__ import annotations

import pytest

from sillo.storage.config import BucketConfig, StorageConfig


def test_bucket_raises_without_a_name_or_default():
    config = StorageConfig(buckets={"attachments": BucketConfig()})
    with pytest.raises(KeyError, match="no bucket named"):
        config.bucket()
