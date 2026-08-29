"""
sillo.mail.context — the mail client :func:`~sillo.mail.client.setup_mail`
built, reachable from anywhere.

The same shape as :mod:`sillo.storage.context`, sharing the same
:class:`~sillo.helpers.registry.InstanceRegistry`. See that module's
docstring for why this exists rather than a lookup through ``app.state``, and
why it has nothing to do with the request lifecycle — mail is sent from queue
jobs and scripts at least as often as from a request handler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..helpers.registry import InstanceRegistry, NotConfiguredError

if TYPE_CHECKING:
    from .client import MailClient

__all__ = ["NotConfiguredError", "current_mail", "register"]

_registry: InstanceRegistry[MailClient] = InstanceRegistry("mail client")

_EXAMPLE = "mail = setup_mail(app, MailConfig(smtp_host=...))"


def register(client: MailClient) -> None:
    """Record *client* as the one to hand back from now on.

    Called by :func:`~sillo.mail.client.setup_mail`; there is no reason to
    call this directly outside a test of the registry itself.

    Args:
        client: What ``setup_mail`` built.
    """
    _registry.register(client)


def current_mail() -> MailClient:
    """The mail client ``setup_mail`` registered.

    Returns:
        The registered :class:`~sillo.mail.client.MailClient`.

    Raises:
        NotConfiguredError: If ``setup_mail`` has not run yet.
    """
    return _registry.current(setup="setup_mail", example=_EXAMPLE)
