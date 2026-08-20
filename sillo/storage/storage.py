"""
sillo.storage.storage — the object on ``app.state``, and how it gets there.

``setup_storage(app, config)`` follows ``setup_record``: build the thing, put it
on ``app.state``, register the lifecycle hooks, return it.  A project holds the
:class:`Storage` and asks it for buckets.
"""

from __future__ import annotations

import logging
from typing import Any

from .bucket import Bucket
from .config import BucketConfig, StorageConfig
from .drivers import LocalDriver, MemoryDriver
from .policies import Private
from .signing import Signer

__all__ = ["Storage", "setup_storage"]

logger = logging.getLogger("sillo.storage")


class Storage:
    """Every bucket a project declared.

    Attributes:
        config: What was declared.
        buckets: The built buckets, by name.
    """

    __slots__ = ("buckets", "config")

    def __init__(self, config: StorageConfig, *, secret: str = "") -> None:
        """Build the buckets a configuration describes.

        Args:
            config: What was declared.
            secret: What signs URLs, when the configuration did not say.

        Raises:
            ValueError: If a bucket names a driver that does not exist.
        """
        self.config = config
        self.buckets: dict[str, Bucket] = {}

        signing_secret = config.secret or secret

        for name, settings in config.buckets.items():
            self.buckets[name] = Bucket(
                name,
                _build(name, settings, signing_secret, config.route),
                policy=settings.policy or Private(),
                max_bytes=settings.max_bytes,
                accepts=settings.accepts,
            )

    def bucket(self, name: str = "") -> Bucket:
        """One bucket.

        Args:
            name: Its name, or empty for the default.

        Returns:
            The bucket.

        Raises:
            KeyError: If no such bucket was declared.
        """
        wanted = name or self.config.default
        self.config.bucket(wanted)
        return self.buckets[wanted]

    def listen(self, listener: Any) -> Any:
        """Be told about every operation, in every bucket.

        Args:
            listener: Called with each
                :class:`~sillo.storage.base.StorageEvent`.

        Returns:
            The listener, so this can be used as a decorator.
        """
        for bucket in self.buckets.values():
            bucket.driver.listen(listener)
        return listener

    async def close(self) -> None:
        """Release every driver."""
        for bucket in self.buckets.values():
            await bucket.driver.close()

    def __repr__(self) -> str:
        """A short description for debugging.

        Returns:
            The bucket names.
        """
        return f"Storage({', '.join(sorted(self.buckets)) or 'no buckets'})"


def _build(name: str, settings: BucketConfig, secret: str, route: str) -> Any:
    """Construct the driver a bucket asked for.

    Args:
        name: The bucket's name.
        settings: Its configuration.
        secret: What signs URLs.
        route: Where the serving route is mounted.

    Returns:
        The driver.

    Raises:
        ValueError: If the driver is unknown, or cannot be built as asked.
    """
    signer = Signer(secret, name) if secret else None

    if settings.driver == "memory":
        return MemoryDriver()

    if settings.driver == "local":
        if not settings.root:
            raise ValueError(f"bucket {name!r} uses the local driver and has no root")

        return LocalDriver(
            settings.root, signer=signer, base_url=f"{route.rstrip('/')}/{name}"
        )

    if settings.driver == "s3":
        raise ValueError(
            f"bucket {name!r} asks for the s3 driver, which needs "
            "sillo-framework[storage-s3]"
        )

    raise ValueError(
        f"bucket {name!r} asks for an unknown driver {settings.driver!r}. "
        "Known: memory, local, s3."
    )


def setup_storage(app: Any, config: StorageConfig, *, secret: str = "") -> Storage:
    """Wire storage into an application.

    Puts the :class:`Storage` on ``app.state["storage"]``, mounts the serving
    route when one is wanted, and registers a shutdown hook.

    Args:
        app: The application.
        config: What to build.
        secret: What signs URLs, when the configuration did not say. Falls back
            to the application's own secret.

    Returns:
        The storage.
    """
    if "storage" in app.state:
        return app.state["storage"]

    storage = Storage(config, secret=secret or _app_secret(app))
    app.state["storage"] = storage
    app.on_shutdown(storage.close)

    if config.serve:
        from .routes import mount

        mount(app, storage, config)

    logger.debug("storage ready — %s", storage)
    return storage


def _app_secret(app: Any) -> str:
    """The application's own secret, if it has one.

    Args:
        app: The application.

    Returns:
        The secret, or an empty string — in which case the buckets are built
        without a signer and say so when asked to sign.
    """
    for name in ("secret_key", "secret"):
        found = getattr(app, name, None) or (app.state or {}).get(name)
        if found:
            return str(found)

    return ""
