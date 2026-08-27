"""
MailClient SMTP transport, templating, and application wiring.

No mail leaves the machine: ``smtplib.SMTP`` and ``SMTP_SSL`` are replaced
with a recorder, so the assertions are about which connection was opened,
which credentials were used, and what was handed to ``sendmail``.
"""

import asyncio
import smtplib

import pytest

from sillo import SilloApp
from sillo.core.http import Request, Response
from sillo.mail import MailClient, MailConfig
from sillo.mail.client import get_mail_client, setup_mail
from sillo.testclient import TestClient


def _run(coro):
    return asyncio.run(coro)


class FakeSMTP:
    """Stand-in for ``smtplib.SMTP`` that records what was asked of it."""

    instances = []

    def __init__(self, host=None, port=None, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.debug_level = 0
        self.login_args = None
        self.sent = []
        self.quit_called = False
        self.noop_calls = 0
        self.noop_fails = False
        FakeSMTP.instances.append(self)

    def starttls(self):
        self.started_tls = True

    def set_debuglevel(self, level):
        self.debug_level = level

    def login(self, username, password):
        self.login_args = (username, password)

    def sendmail(self, sender, recipients, body):
        self.sent.append((sender, recipients, body))

    def noop(self):
        self.noop_calls += 1
        if self.noop_fails:
            raise smtplib.SMTPServerDisconnected("connection lost")
        return (250, b"OK")

    def quit(self):
        self.quit_called = True


class FakeSMTPSSL(FakeSMTP):
    pass


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTPSSL)
    return FakeSMTP


def _client(**overrides):
    settings = {
        "smtp_host": "mail.example.com",
        "smtp_port": 25,
        "default_from": "noreply@example.com",
        "suppress_send": False,
        "use_tls": False,
    }
    settings.update(overrides)
    return MailClient(MailConfig(**settings))


def _decoded(raw: str) -> str:
    """The MIME parts are base64-encoded; return the whole message as text."""
    import email

    parsed = email.message_from_string(raw)
    parts = parsed.walk() if parsed.is_multipart() else [parsed]
    return "\n".join(
        part.get_payload(decode=True).decode("utf-8", "replace")
        for part in parts
        if part.get_payload(decode=True)
    )


# ── connecting ───────────────────────────────────────────────────────────


def test_starting_opens_a_connection():
    client = _client()
    _run(client.start())
    assert len(FakeSMTP.instances) == 1


def test_the_host_and_port_are_passed_through():
    client = _client()
    _run(client.start())
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "mail.example.com"
    assert smtp.port == 25


def test_the_timeout_is_passed_through():
    client = _client(smtp_timeout=12.5)
    _run(client.start())
    assert FakeSMTP.instances[0].timeout == 12.5


def test_tls_is_negotiated_when_enabled():
    client = _client(use_tls=True)
    _run(client.start())
    assert FakeSMTP.instances[0].started_tls is True


def test_tls_is_not_negotiated_when_disabled():
    client = _client(use_tls=False)
    _run(client.start())
    assert FakeSMTP.instances[0].started_tls is False


def test_ssl_uses_the_implicit_tls_class():
    """SSL connects on an already-encrypted socket, so no STARTTLS upgrade."""
    client = _client(use_ssl=True, use_tls=False, smtp_port=465)
    _run(client.start())
    smtp = FakeSMTP.instances[0]
    assert isinstance(smtp, FakeSMTPSSL)
    assert smtp.started_tls is False


def test_the_submission_port_implies_starttls():
    """Port 587 is the submission port; STARTTLS is switched on for it even if
    the config left it off."""
    client = _client(smtp_port=587, use_tls=False)
    _run(client.start())
    assert client.config.use_tls is True
    assert FakeSMTP.instances[0].started_tls is True


def test_the_smtps_port_implies_implicit_tls():
    client = _client(smtp_port=465, use_tls=False)
    _run(client.start())
    assert client.config.use_ssl is True
    assert isinstance(FakeSMTP.instances[0], FakeSMTPSSL)


def test_ssl_and_tls_together_are_rejected():
    with pytest.raises(ValueError, match="both"):
        MailConfig(use_ssl=True, use_tls=True)


def test_credentials_are_used_when_both_are_present():
    client = _client(smtp_username="user", smtp_password="pass")
    _run(client.start())
    assert FakeSMTP.instances[0].login_args == ("user", "pass")


def test_no_login_without_a_password():
    client = _client(smtp_username="user", smtp_password=None)
    _run(client.start())
    assert FakeSMTP.instances[0].login_args is None


def test_debug_mode_turns_on_smtp_tracing():
    client = _client(debug=True)
    _run(client.start())
    assert FakeSMTP.instances[0].debug_level == 1


def test_starting_twice_reuses_the_connection():
    client = _client()
    _run(client.start())
    _run(client.start())
    assert len(FakeSMTP.instances) == 1


def test_a_suppressed_client_never_connects():
    client = MailClient(MailConfig(suppress_send=True, default_from="a@example.com"))
    _run(client.start())
    assert FakeSMTP.instances == []


# ── stopping ─────────────────────────────────────────────────────────────


def test_stopping_quits_the_connection():
    client = _client()
    _run(client.start())
    _run(client.stop())
    assert FakeSMTP.instances[0].quit_called is True


def test_stopping_a_client_that_never_started_is_a_no_op():
    client = _client()
    _run(client.stop())
    assert FakeSMTP.instances == []


def test_stopping_twice_is_safe():
    client = _client()
    _run(client.start())
    _run(client.stop())
    _run(client.stop())
    assert FakeSMTP.instances[0].quit_called is True


def test_a_failure_while_quitting_is_swallowed():
    """A dead socket must not turn shutdown into an error."""
    client = _client()
    _run(client.start())

    def explode():
        raise smtplib.SMTPServerDisconnected("already gone")

    FakeSMTP.instances[0].quit = explode
    _run(client.stop())


def test_restarting_after_a_stop_opens_a_new_connection():
    client = _client()
    _run(client.start())
    _run(client.stop())
    _run(client.start())
    assert len(FakeSMTP.instances) == 2


# ── sending ──────────────────────────────────────────────────────────────


def test_a_message_reaches_sendmail():
    client = _client()
    _run(client.start())
    result = _run(client.send_email(to="a@example.com", subject="Hi", body="Hello"))
    assert result.success is True
    assert len(FakeSMTP.instances[0].sent) == 1


def test_the_envelope_sender_is_the_configured_default():
    client = _client()
    _run(client.start())
    _run(client.send_email(to="a@example.com", subject="Hi", body="Hello"))
    sender, _, _ = FakeSMTP.instances[0].sent[0]
    assert "noreply@example.com" in sender


def test_an_explicit_sender_wins():
    client = _client()
    _run(client.start())
    _run(
        client.send_email(
            to="a@example.com", subject="Hi", body="x", from_email="me@example.com"
        )
    )
    sender, _, _ = FakeSMTP.instances[0].sent[0]
    assert "me@example.com" in sender


def test_cc_and_bcc_are_in_the_envelope():
    """Both have to reach the server even though only Cc appears in the body."""
    client = _client()
    _run(client.start())
    _run(
        client.send_email(
            to="a@example.com",
            subject="Hi",
            body="x",
            cc="c@example.com",
            bcc="b@example.com",
        )
    )
    _, recipients, _ = FakeSMTP.instances[0].sent[0]
    assert set(recipients) == {"a@example.com", "c@example.com", "b@example.com"}


def test_bcc_is_not_written_into_the_headers():
    client = _client()
    _run(client.start())
    _run(
        client.send_email(
            to="a@example.com", subject="Hi", body="x", bcc="hidden@example.com"
        )
    )
    _, _, body = FakeSMTP.instances[0].sent[0]
    assert "hidden@example.com" not in body.split("\n\n", 1)[0]


def test_configured_default_cc_is_applied():
    client = _client(default_cc=["always@example.com"])
    _run(client.start())
    _run(client.send_email(to="a@example.com", subject="Hi", body="x"))
    _, recipients, _ = FakeSMTP.instances[0].sent[0]
    assert "always@example.com" in recipients


def test_configured_default_bcc_is_applied():
    client = _client(default_bcc=["archive@example.com"])
    _run(client.start())
    _run(client.send_email(to="a@example.com", subject="Hi", body="x"))
    _, recipients, _ = FakeSMTP.instances[0].sent[0]
    assert "archive@example.com" in recipients


def test_an_explicit_cc_suppresses_the_default():
    client = _client(default_cc=["always@example.com"])
    _run(client.start())
    _run(client.send_email(to="a@example.com", subject="Hi", body="x", cc="me@x.com"))
    _, recipients, _ = FakeSMTP.instances[0].sent[0]
    assert "always@example.com" not in recipients


def test_sending_connects_on_demand():
    """``send`` before ``start`` still works rather than erroring."""
    client = _client()
    result = _run(client.send_email(to="a@example.com", subject="Hi", body="x"))
    assert result.success is True
    assert len(FakeSMTP.instances) == 1


def test_a_dropped_connection_is_re_established():
    client = _client()
    _run(client.start())
    FakeSMTP.instances[0].noop_fails = True
    result = _run(client.send_email(to="a@example.com", subject="Hi", body="x"))
    assert result.success is True
    assert len(FakeSMTP.instances) == 2


def test_a_live_connection_is_reused():
    client = _client()
    _run(client.start())
    _run(client.send_email(to="a@example.com", subject="one", body="x"))
    _run(client.send_email(to="a@example.com", subject="two", body="x"))
    assert len(FakeSMTP.instances) == 1
    assert len(FakeSMTP.instances[0].sent) == 2


def test_an_smtp_failure_is_reported_not_raised():
    client = _client()
    _run(client.start())

    def refuse(sender, recipients, body):
        raise smtplib.SMTPRecipientsRefused({"a@example.com": (550, b"No such user")})

    FakeSMTP.instances[0].sendmail = refuse
    result = _run(client.send_email(to="a@example.com", subject="Hi", body="x"))
    assert result.success is False
    assert result.error


def test_a_missing_sender_is_an_error_result():
    client = MailClient(MailConfig(default_from=None, suppress_send=True))
    result = _run(client.send_email(to="a@example.com", subject="Hi", body="x"))
    assert result.success is False
    assert "from" in result.error.lower()


def test_the_failed_result_still_carries_the_recipients():
    client = MailClient(MailConfig(default_from=None, suppress_send=True))
    result = _run(client.send_email(to="a@example.com", subject="Hi", body="x"))
    assert result.to == ["a@example.com"]


# ── templates ────────────────────────────────────────────────────────────


@pytest.fixture
def template_dir(tmp_path):
    (tmp_path / "welcome.html").write_text("<p>Hello {{ name }}</p>")
    (tmp_path / "welcome.txt").write_text("Hello {{ name }}")
    (tmp_path / "html_only.html").write_text("<p>Only HTML for {{ name }}</p>")
    return tmp_path


def test_a_template_directory_is_loaded(template_dir):
    client = MailClient(
        MailConfig(
            template_directory=str(template_dir),
            default_from="a@example.com",
            suppress_send=True,
        )
    )
    assert client._template_env is not None


def test_a_missing_template_directory_is_tolerated(tmp_path):
    """A misconfigured path must not stop the app from booting."""
    client = MailClient(
        MailConfig(
            template_directory=str(tmp_path / "nope"),
            default_from="a@example.com",
            suppress_send=True,
        )
    )
    assert client._template_env is None


def test_the_html_template_is_rendered(template_dir):
    client = _client(template_directory=str(template_dir))
    _run(client.start())
    _run(
        client.send_template_email(
            to="a@example.com",
            subject="Welcome",
            template_name="welcome",
            context={"name": "Ada"},
        )
    )
    _, _, raw = FakeSMTP.instances[0].sent[0]
    assert "Ada" in _decoded(raw)


def test_the_text_alternative_is_rendered_when_present(template_dir):
    client = MailClient(
        MailConfig(
            template_directory=str(template_dir),
            default_from="a@example.com",
            suppress_send=True,
        )
    )
    from sillo.mail import EmailMessage

    message = EmailMessage(
        to="a@example.com",
        subject="Welcome",
        template_name="welcome",
        template_context={"name": "Ada"},
    )
    _run(client.send_message(message))
    assert message.body == "Hello Ada"
    assert "<p>Hello Ada</p>" in message.html_body


def test_a_template_without_a_text_alternative_still_sends(template_dir):
    client = _client(template_directory=str(template_dir))
    _run(client.start())
    result = _run(
        client.send_template_email(
            to="a@example.com",
            subject="Welcome",
            template_name="html_only",
            context={"name": "Ada"},
        )
    )
    assert result.success is True


def test_a_missing_template_is_reported_as_a_failure(template_dir):
    client = _client(template_directory=str(template_dir))
    _run(client.start())
    result = _run(
        client.send_template_email(
            to="a@example.com", subject="X", template_name="no_such_template"
        )
    )
    assert result.success is False


def test_a_malformed_template_is_reported_as_a_failure(template_dir):
    """A jinja2.TemplateError (e.g. bad syntax) must fail the send, not raise
    out of send_message()."""
    (template_dir / "broken.html").write_text("{% if %}")
    client = _client(template_directory=str(template_dir))
    _run(client.start())
    result = _run(
        client.send_template_email(
            to="a@example.com", subject="X", template_name="broken"
        )
    )
    assert result.success is False


def test_autoescaping_is_on_by_default(template_dir):
    (template_dir / "escaped.html").write_text("<p>{{ value }}</p>")
    client = MailClient(
        MailConfig(
            template_directory=str(template_dir),
            default_from="a@example.com",
            suppress_send=True,
        )
    )
    from sillo.mail import EmailMessage

    message = EmailMessage(
        to="a@example.com",
        subject="X",
        template_name="escaped",
        template_context={"value": "<script>alert(1)</script>"},
    )
    _run(client.send_message(message))
    assert "<script>" not in message.html_body


# ── application wiring ───────────────────────────────────────────────────


def test_setup_mail_registers_a_client():
    app = SilloApp()
    client = setup_mail(app, MailConfig(suppress_send=True))
    assert app.state["mail_client"] is client


def test_setup_mail_is_idempotent():
    app = SilloApp()
    first = setup_mail(app, MailConfig(suppress_send=True))
    second = setup_mail(app, MailConfig(suppress_send=True))
    assert first is second


def test_the_client_is_started_and_stopped_with_the_app():
    app = SilloApp()
    client = setup_mail(app, MailConfig(suppress_send=True))
    with TestClient(app):
        assert client._started is True
    assert client._started is False


def test_a_handler_can_reach_the_client(test_client_factory):
    app = SilloApp()
    setup_mail(app, MailConfig(default_from="a@example.com", suppress_send=True))

    @app.get("/send")
    async def send(request: Request, response: Response):
        client = get_mail_client(request)
        result = await client.send_email(to="b@example.com", subject="Hi", body="x")
        return response.json({"sent": result.success})

    with test_client_factory(app) as http:
        assert http.get("/send").json() == {"sent": True}


def test_asking_for_an_unconfigured_client_is_an_explicit_error(test_client_factory):
    app = SilloApp()

    @app.get("/send")
    async def send(request: Request, response: Response):
        get_mail_client(request)
        return response.json({})

    with test_client_factory(app, raise_server_exceptions=False) as http:
        assert http.get("/send").status_code == 500
