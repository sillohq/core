"""
sillo.storage.routes — serving what was stored, and honouring signatures.

Two jobs.  It is the endpoint every local signed URL points at, and it is the
half of content-type sniffing that makes sniffing a defence rather than a
label: the sniffed type only matters if the browser is told not to re-sniff.

So every response carries:

``X-Content-Type-Options: nosniff``
    Without it a browser will look at the bytes and reach its own conclusion,
    and the whole sniffing chain was pointless.

``Content-Disposition``
    ``attachment`` for anything not on a small render-safe list, so an
    unexpected type downloads rather than executing in this origin.

``Content-Security-Policy: sandbox``
    A last line under the other two, for the case where a type on the safe list
    turns out to have been a mistake.

Even so: a bucket serving files from users, on the same origin as the
application, is a risk that headers reduce and do not remove.  A public bucket
belongs on another origin.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import unquote

from sillo.responses import json, stream

from .config import StorageConfig
from .errors import FileNotFound, PolicyRefused, SignatureInvalid, UnsafeKey

__all__ = ["mount"]

logger = logging.getLogger("sillo.storage")

#: Types a browser may render inline. Everything else is sent as an attachment.
#: Short and closed on purpose — this list is the blast radius.
INLINE = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "application/pdf",
        "text/plain",
        "text/csv",
    }
)

#: Headers on every response.
GUARDS: tuple[tuple[str, str], ...] = (
    ("x-content-type-options", "nosniff"),
    ("content-security-policy", "sandbox; default-src 'none'"),
    ("referrer-policy", "no-referrer"),
    ("cross-origin-resource-policy", "same-origin"),
)


def mount(app: Any, storage: Any, config: StorageConfig) -> None:
    """Register the route that serves stored objects.

    Args:
        app: The application.
        storage: The built :class:`~sillo.storage.storage.Storage`.
        config: What was declared.
    """
    route = config.route.rstrip("/")

    async def serve(ctx, bucket: str, key: str):
        """Serve one object, if the caller may have it.

        Args:
            request: The incoming request.
            response: The responder.
            bucket: Which bucket.
            key: Which object.

        Returns:
            The object, or a refusal.
        """
        try:
            held = storage.bucket(bucket)
        except KeyError:
            return json({"detail": "Not found"}, status_code=404)

        signed = False
        token = ctx.query_params.get("token") if hasattr(ctx, "query_params") else None

        if token:
            try:
                held.driver._signer.verify(token, key=key, method="GET")
                signed = True
            except (SignatureInvalid, AttributeError):
                return json({"detail": "Not found"}, status_code=404)

        try:
            info = await held.stat(key, user=_user(ctx), signed=signed)
        except (FileNotFound, UnsafeKey):
            # One answer for "no such object" and "not yours". A 403 on a
            # private bucket confirms the object exists, which is half of what
            # somebody probing for it wants to know.
            return json({"detail": "Not found"}, status_code=404)
        except PolicyRefused:
            return json({"detail": "Not found"}, status_code=404)

        disposition = "inline" if info.content_type in INLINE else "attachment"
        filename = key.rsplit("/", 1)[-1]

        # Not in `headers`: `Responder.stream` takes `content_type` as its own
        # argument, defaults it to text/plain, and hands that to the response —
        # so a content type set here is silently overridden, and every sniffed
        # type was arriving as text/plain.
        headers = {
            "content-length": str(info.size),
            "etag": f'"{info.etag}"',
            "content-disposition": f'{disposition}; filename="{_quote(filename)}"',
            "cache-control": "private, max-age=0, must-revalidate",
            **dict(GUARDS),
        }

        return stream(
            held.get(key, user=_user(ctx), signed=signed),
            content_type=info.content_type,
            headers=headers,
        )

    app.get(f"{route}/{{bucket}}/{{key:path}}", handler=serve, name="storage.serve")


def _user(ctx: Any) -> Any:
    """Who is asking, if anybody.

    ``ctx.user`` is a property that *raises* when no authentication
    middleware is installed, so ``getattr(request, "user", None)`` does not
    protect against it — the default is never reached because the lookup does
    not fail, it throws. An application serving a public bucket and running no
    auth at all is entirely reasonable, and it was getting a 500.

    Args:
        request: The incoming request.

    Returns:
        The authenticated user, or None when there is no auth configured.
    """
    try:
        return ctx.user
    except (ValueError, AttributeError, AssertionError):
        return None


def _quote(filename: str) -> str:
    """Make a filename safe to put in a header.

    A quote or a newline in a ``Content-Disposition`` is header injection, and
    the filename came from whoever uploaded the file.

    Args:
        filename: The object's last segment.

    Returns:
        Something safe between quotes.
    """
    cleaned = unquote(filename).replace("\\", "").replace('"', "")
    return "".join(character for character in cleaned if character.isprintable())
