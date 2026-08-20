"""
sillo.mail.context, wired through setup_mail.

Same shape as tests/test_storage/test_context.py — the primitive itself is
covered in test_internals/test_registry.py; this proves setup_mail actually
registers the client and that send_email()/current_mail() reach it with no
request in hand, which matters more here than for storage: mail is sent from
queue jobs at least as often as from a request handler.
"""

from __future__ import annotations

import asyncio

import pytest

from sillo import SilloApp
from sillo._internals.registry import InstanceRegistry
from sillo.mail import (
    MailConfig,
    NotConfiguredError,
    current_mail,
    send_email,
    setup_mail,
)
from sillo.mail import context as mail_context


def _make_client(default_from: str):
    application = SilloApp(title="Context")
    return setup_mail(
        application, MailConfig(default_from=default_from, suppress_send=True)
    )


def test_send_email_is_reachable_right_after_setup_mail():
    """No request, no app.get, no middleware — just setup_mail then send_email()."""
    _make_client("noreply-a@example.com")

    result = asyncio.run(send_email("someone@example.com", "Hi", body="Hello"))
    assert result.success is True


def test_current_mail_matches_what_setup_mail_returned():
    client = _make_client("noreply-a@example.com")

    assert current_mail() is client


def test_send_email_is_reachable_from_a_plain_function_no_request_involved():
    """Stands in for a queue job: a plain function with no request at all."""
    _make_client("noreply-a@example.com")

    async def deep_in_a_queue_job() -> bool:
        result = await send_email("someone@example.com", "Hi", body="Hello")
        return result.success

    assert asyncio.run(deep_in_a_queue_job()) is True


def test_current_mail_before_setup_mail_raises(monkeypatch):
    """A fresh registry, so this does not depend on test order."""
    monkeypatch.setattr(mail_context, "_registry", InstanceRegistry("mail client"))

    with pytest.raises(NotConfiguredError) as excinfo:
        mail_context.current_mail()

    message = str(excinfo.value)
    assert "setup_mail" in message
    assert "mail client" in message


def test_a_second_setup_mail_call_replaces_the_registered_client():
    """setup_mail is process-global, not per-application — see the matching
    storage test for why that is the deliberate trade of not being tied to
    any request or app object."""
    _make_client("noreply-a@example.com")
    client_b = _make_client("noreply-b@example.com")

    assert current_mail() is client_b
