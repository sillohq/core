"""
sillo.storage.drivers — the backends.

``memory`` and ``local`` ship in the core; ``s3`` arrives with the
``sillo[storage-s3]`` extra. A project needing something else writes a
:class:`~sillo.storage.base.Driver` subclass and runs it against the same
contract suite the shipped ones are held to.
"""

from __future__ import annotations

from .local import LocalDriver
from .memory import MemoryDriver

__all__ = ["LocalDriver", "MemoryDriver"]
