import asyncio
import pytest
from sillo.mail import (
    MailConfig,
    MailClient,
    EmailMessage,
    EmailResult,
    EmailAttachment,
)


def _run(coro):
    return asyncio.run(coro)


class TestMailConfig:
    def test_default_config(self):
        c = MailConfig()
        assert c.smtp_host == "localhost"
        assert c.smtp_port == 587
        assert c.use_tls is True
        assert c.use_ssl is False

    def test_ssl_tls_mutual_exclusion(self):
        with pytest.raises(ValueError):
            MailConfig(use_tls=True, use_ssl=True)

    def test_port_465_auto_ssl(self):
        c = MailConfig(smtp_port=465, use_tls=False, use_ssl=False)
        assert c.use_ssl is True
        assert c.use_tls is False

    def test_port_587_auto_tls(self):
        c = MailConfig(smtp_port=587, use_tls=False, use_ssl=False)
        assert c.use_tls is True
        assert c.use_ssl is False

    def test_for_gmail(self):
        c = MailConfig.for_gmail("u", "p")
        assert c.smtp_host == "smtp.gmail.com"
        assert c.smtp_port == 587

    def test_for_outlook(self):
        c = MailConfig.for_outlook("u", "p")
        assert c.smtp_host == "smtp-mail.outlook.com"

    def test_for_sendgrid(self):
        c = MailConfig.for_sendgrid("key")
        assert c.smtp_host == "smtp.sendgrid.net"
        assert c.smtp_username == "apikey"

    def test_to_dict_masks_password(self):
        c = MailConfig(smtp_password="secret")
        assert c.to_dict()["smtp_password"] == "***"


class TestEmailMessage:
    def test_basic_message(self):
        m = EmailMessage(to="a@b.com", subject="Test", body="Hello")
        assert m.to == ["a@b.com"]
        assert m.subject == "Test"

    def test_string_to_normalizes_to_list(self):
        m = EmailMessage(to="a@b.com", subject="T", cc="c@d.com")
        assert m.to == ["a@b.com"]
        assert m.cc == ["c@d.com"]

    def test_add_attachment(self):
        m = EmailMessage(to="a@b.com", subject="T")
        m.add_attachment("f.txt", b"hello", content_type="text/plain")
        assert len(m.attachments) == 1
        assert m.attachments[0].filename == "f.txt"

    def test_add_header(self):
        m = EmailMessage(to="a@b.com", subject="T")
        m.add_header("X-Custom", "val")
        assert m.headers["X-Custom"] == "val"

    def test_to_mime_message(self):
        m = EmailMessage(to="a@b.com", subject="Hello", body="World", from_email="me@x.com")
        msg = m.to_mime_message()
        assert msg["Subject"] == "Hello"
        assert msg["From"] == "me@x.com"
        assert msg["To"] == "a@b.com"

    def test_to_mime_with_priority(self):
        m = EmailMessage(to="a@b.com", subject="T", priority=1)
        msg = m.to_mime_message()
        assert msg["X-Priority"] == "1"

    def test_to_mime_with_cc_reply_to(self):
        m = EmailMessage(to="a@b.com", subject="T", cc=["c@d.com"], reply_to=["r@x.com"])
        msg = m.to_mime_message()
        assert msg["Cc"] == "c@d.com"
        assert msg["Reply-To"] == "r@x.com"


class TestEmailResult:
    def test_success_result(self):
        r = EmailResult(success=True, message_id="1", to=["a@b.com"], subject="T")
        d = r.to_dict()
        assert d["success"] is True
        assert d["message_id"] == "1"

    def test_failure_result(self):
        r = EmailResult(success=False, message_id="2", to=["a@b.com"], subject="T", error="SMTP down")
        d = r.to_dict()
        assert d["success"] is False
        assert d["error"] == "SMTP down"


class TestMailClient:
    def test_suppress_send(self):
        client = MailClient(config=MailConfig(suppress_send=True))
        result = _run(client.send_message(
            EmailMessage(to="a@b.com", subject="T", body="Hello", from_email="me@x.com")
        ))
        assert result.success is True
        assert result.provider_response == {"suppressed": True}

    def test_missing_from_raises(self):
        client = MailClient(config=MailConfig(suppress_send=True))
        result = _run(client.send_message(
            EmailMessage(to="a@b.com", subject="T", body="Hello")
        ))
        assert result.success is False
        assert "No 'from'" in result.error
