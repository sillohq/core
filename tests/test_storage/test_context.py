"""
sillo.storage.context, wired through setup_storage.

test_helpers/test_registry.py already proves the primitive is sound on its
own; what is worth proving here is the wiring itself — that setup_storage
actually registers the instance, that bucket()/current_storage() reach it with
no request or app in hand, and that the last application to call setup_storage
in a process is the one they return.
"""

from __future__ import annotations

import pytest

from sillo import SilloApp
from sillo.storage import (
    BucketConfig,
    NotConfiguredError,
    Public,
    StorageConfig,
    bucket,
    current_storage,
    setup_storage,
)

SECRET = "an-application-secret-long-enough"


def _make_app(tmp_path, default: str):
    application = SilloApp(title="Context")
    application.state["secret_key"] = SECRET

    storage = setup_storage(
        application,
        StorageConfig(
            default=default,
            buckets={
                default: BucketConfig(
                    driver="local", root=str(tmp_path / default), policy=Public()
                ),
            },
        ),
    )
    return application, storage


def test_bucket_is_reachable_right_after_setup_storage(tmp_path):
    """No request, no app call, no middleware — just setup_storage then bucket()."""
    _make_app(tmp_path, "attachments")

    assert bucket().name == "attachments"


def test_current_storage_matches_what_setup_storage_returned(tmp_path):
    _application, storage = _make_app(tmp_path, "attachments")

    assert current_storage() is storage


def test_bucket_is_reachable_from_a_plain_function_no_request_involved(tmp_path):
    """Stands in for a queue job or script: a function with no request at all."""
    _make_app(tmp_path, "attachments")

    def deep_in_a_queue_job() -> str:
        return bucket().name

    assert deep_in_a_queue_job() == "attachments"


def test_current_storage_before_setup_storage_raises(monkeypatch, tmp_path):
    """A fresh registry, so this does not depend on test order."""
    from sillo.helpers.registry import InstanceRegistry
    from sillo.storage import context as storage_context

    monkeypatch.setattr(storage_context, "_registry", InstanceRegistry("storage"))

    with pytest.raises(NotConfiguredError) as excinfo:
        storage_context.current_storage()

    message = str(excinfo.value)
    assert "setup_storage" in message
    assert "storage" in message


def test_a_second_setup_storage_call_replaces_the_registered_instance(tmp_path):
    """setup_storage is process-global, not per-application.

    Calling it again — a second application in the same process, the shape a
    test suite makes — replaces what bucket()/current_storage() return. This
    is a deliberate consequence of not being tied to any request or app
    object: there is exactly one registered storage at a time.
    """
    _make_app(tmp_path / "a", "receipts")
    _application_b, storage_b = _make_app(tmp_path / "b", "avatars")

    assert current_storage() is storage_b
    assert bucket().name == "avatars"
