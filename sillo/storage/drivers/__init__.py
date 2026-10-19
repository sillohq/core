"""
sillo.storage.drivers — the backends.

``memory`` and ``local`` ship in the core; ``s3`` arrives with the
``sillo[storage-s3]`` extra. A project needing something else writes a
:class:`~sillo.storage.base.Driver` subclass and runs it against the same
contract suite the shipped ones are held to.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .local import LocalDriver
from .memory import MemoryDriver

if TYPE_CHECKING:
    from .s3 import S3Driver

__all__ = ["LocalDriver", "MemoryDriver", "S3Driver"]


def __getattr__(name: str) -> object:
    if name == "S3Driver":
        from .s3 import S3Driver

        return S3Driver
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
