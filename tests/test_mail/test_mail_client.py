"""
MailClient send paths.

``suppress_send`` lets the whole compose-and-address pipeline run without an
SMTP server, so these cover defaults, recipient normalization, attachments,
and failure handling. The one place a real connection would be made is
stubbed, which keeps the tests hermetic and fast.
"""

import asyncio

import pytest

from sillo.mail import EmailAttachment, EmailMessage, MailClient, MailConfig


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def config():
    return MailConfig(
        default_from="noreply@example.com",
        suppress_send=True,
    )


@pytest.fixture
def client(config):
    return MailClient(config)


# ── suppressed sending ───────────────────────────────────────────────────


def test_suppressed_send_reports_success(client):
    result = _run(client.send_email(to="a@example.com", subject="Hi", body="Hello"))
    assert result.success is True
    assert result.error is None


def test_suppressed_send_records_the_recipients(client):
    result = _run(client.send_email(to="a@example.com", subject="Hi", body="Hello"))
    assert "a@example.com" in result.to


def test_suppressed_send_records_the_subject(client):
    result = _run(client.send_email(to="a@example.com", subject="Hi", body="x"))
    assert result.subject == "Hi"


def test_a_single_recipient_string_is_accepted(client):
    result = _run(client.send_email(to="solo@example.com", subject="s", body="b"))
    assert result.success is True


def test_a_recipient_list_is_accepted(client):
    result = _run(
        client.send_email(to=["a@example.com", "b@example.com"], subject="s", body="b")
    )
    assert result.success is True


def test_html_body(client):
    result = _run(
        client.send_email(to="a@example.com", subject="s", html_body="<b>hi</b>")
    )
    assert result.success is True


def test_both_bodies(client):
    result = _run(
        client.send_email(
            to="a@example.com", subject="s", body="plain", html_body="<b>rich</b>"
        )
    )
    assert result.success is True


# ── addressing ───────────────────────────────────────────────────────────


def test_missing_from_address_fails_cleanly():
    """No default and no explicit sender is an error, not a crash."""
    client = MailClient(MailConfig(suppress_send=True))
    result = _run(client.send_email(to="a@example.com", subject="s", body="b"))
    assert result.success is False
    assert result.error is not None


def test_explicit_from_overrides_the_default(client):
    result = _run(
        client.send_email(
            to="a@example.com", subject="s", body="b", from_email="other@example.com"
        )
    )
    assert result.success is True


def test_default_cc_is_applied():
    client = MailClient(
        MailConfig(
            default_from="from@example.com",
            default_cc=["cc@example.com"],
            suppress_send=True,
        )
    )
    result = _run(client.send_email(to="a@example.com", subject="s", body="b"))
    assert result.success is True


def test_default_bcc_is_applied():
    client = MailClient(
        MailConfig(
            default_from="from@example.com",
            default_bcc=["bcc@example.com"],
            suppress_send=True,
        )
    )
    result = _run(client.send_email(to="a@example.com", subject="s", body="b"))
    assert result.success is True


def test_explicit_cc_takes_precedence_over_the_default():
    client = MailClient(
        MailConfig(
            default_from="from@example.com",
            default_cc=["default-cc@example.com"],
            suppress_send=True,
        )
    )
    msg = EmailMessage(
        to=["a@example.com"], subject="s", body="b", cc=["explicit@example.com"]
    )
    assert _run(client.send_message(msg)).success is True


def test_reply_to(client):
    result = _run(
        client.send_email(
            to="a@example.com", subject="s", body="b", reply_to="reply@example.com"
        )
    )
    assert result.success is True


# ── attachments ──────────────────────────────────────────────────────────


def test_attachment(client):
    msg = EmailMessage(
        to=["a@example.com"],
        subject="s",
        body="b",
        attachments=[
            EmailAttachment(
                filename="note.txt", content=b"hello", content_type="text/plain"
            )
        ],
    )
    assert _run(client.send_message(msg)).success is True


def test_several_attachments(client):
    msg = EmailMessage(
        to=["a@example.com"],
        subject="s",
        body="b",
        attachments=[
            EmailAttachment(filename="a.txt", content=b"a", content_type="text/plain"),
            EmailAttachment(filename="b.bin", content=b"\x00\x01"),
        ],
    )
    assert _run(client.send_message(msg)).success is True


# ── failure handling ─────────────────────────────────────────────────────


async def _noop_connect(self=None):
    return None


def test_transport_failure_is_reported_not_raised(monkeypatch):
    """A dead SMTP server must produce a failed result, not an exception."""
    client = MailClient(MailConfig(default_from="from@example.com"))

    def boom(*args, **kwargs):
        raise ConnectionError("smtp is down")

    monkeypatch.setattr(client, "_ensure_connected", _noop_connect)
    monkeypatch.setattr(client, "_send_mime", boom)

    result = _run(client.send_email(to="a@example.com", subject="s", body="b"))
    assert result.success is False
    assert "smtp is down" in str(result.error)


def test_a_successful_transport_reports_success(monkeypatch):
    client = MailClient(MailConfig(default_from="from@example.com"))
    sent = {}

    def capture(mime_message, recipients):
        sent["recipients"] = recipients

    monkeypatch.setattr(client, "_ensure_connected", _noop_connect)
    monkeypatch.setattr(client, "_send_mime", capture)

    result = _run(client.send_email(to="a@example.com", subject="s", body="b"))
    assert result.success is True
    assert "a@example.com" in sent["recipients"]


def test_cc_and_bcc_reach_the_transport_recipient_list(monkeypatch):
    """Blind copies must be delivered even though they are not in the headers."""
    client = MailClient(MailConfig(default_from="from@example.com"))
    sent = {}
    monkeypatch.setattr(client, "_ensure_connected", _noop_connect)
    monkeypatch.setattr(
        client, "_send_mime", lambda m, r: sent.__setitem__("recipients", r)
    )

    msg = EmailMessage(
        to=["a@example.com"],
        subject="s",
        body="b",
        cc=["c@example.com"],
        bcc=["d@example.com"],
    )
    _run(client.send_message(msg))

    assert set(sent["recipients"]) >= {"a@example.com", "c@example.com", "d@example.com"}


# ── lifecycle ────────────────────────────────────────────────────────────


def test_start_and_stop_are_safe_to_call(client):
    _run(client.start())
    _run(client.stop())


def test_client_without_a_config_uses_defaults():
    assert MailClient().config.smtp_host == "localhost"


def test_send_email_accepts_dict_form_attachments(client):
    result = _run(
        client.send_email(
            to="a@example.com",
            subject="s",
            body="b",
            attachments=[
                {"filename": "note.txt", "content": b"hi", "content_type": "text/plain"}
            ],
        )
    )
    assert result.success is True


def test_send_email_accepts_object_form_attachments(client):
    result = _run(
        client.send_email(
            to="a@example.com",
            subject="s",
            body="b",
            attachments=[
                EmailAttachment(
                    filename="note.txt", content=b"hi", content_type="text/plain"
                )
            ],
        )
    )
    assert result.success is True


def test_ensure_connected_is_a_noop_when_sending_is_suppressed(client):
    _run(client._ensure_connected())
    assert client._smtp is None


def test_send_mime_raises_when_not_connected(client):
    with pytest.raises(RuntimeError, match="SMTP not connected"):
        client._send_mime(mime_message=None, recipients=[])


def test_render_template_is_a_noop_without_a_template_env(client):
    msg = EmailMessage(to=["a@example.com"], subject="s", body="b")
    # client has no template_directory configured, so _template_env is None.
    client._render_template(msg)
    assert msg.html_body is None
