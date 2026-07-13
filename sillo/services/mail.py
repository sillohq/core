from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("sillo.services.mail")

try:
    import jinja2
    _JINJA2 = True
except ImportError:
    _JINJA2 = False


# ── Config ───────────────────────────────────────────────────────────────────


@dataclass
class MailConfig:
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "localhost"))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_username: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_USERNAME"))
    smtp_password: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_PASSWORD"))
    use_tls: bool = field(default_factory=lambda: os.getenv("SMTP_USE_TLS", "true").lower() == "true")
    use_ssl: bool = field(default_factory=lambda: os.getenv("SMTP_USE_SSL", "false").lower() == "true")
    default_from: Optional[str] = field(default_factory=lambda: os.getenv("MAIL_DEFAULT_FROM"))
    default_reply_to: Optional[str] = field(default_factory=lambda: os.getenv("MAIL_DEFAULT_REPLY_TO"))
    default_cc: Optional[List[str]] = None
    default_bcc: Optional[List[str]] = None
    smtp_timeout: float = field(default_factory=lambda: float(os.getenv("SMTP_TIMEOUT", "30")))
    max_connections: int = field(default_factory=lambda: int(os.getenv("SMTP_MAX_CONNECTIONS", "10")))
    template_directory: Optional[str] = field(default_factory=lambda: os.getenv("MAIL_TEMPLATE_DIR"))
    template_auto_escape: bool = True
    debug: bool = field(default_factory=lambda: os.getenv("MAIL_DEBUG", "false").lower() == "true")
    suppress_send: bool = field(default_factory=lambda: os.getenv("MAIL_SUPPRESS_SEND", "false").lower() == "true")

    def __post_init__(self) -> None:
        if self.use_ssl and self.use_tls:
            raise ValueError("Cannot use both SSL and TLS")
        if self.smtp_port == 465 and not self.use_ssl:
            self.use_ssl, self.use_tls = True, False
        elif self.smtp_port == 587 and not self.use_tls:
            self.use_tls, self.use_ssl = True, False

    def to_dict(self) -> Dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items()}
        if d.get("smtp_password"):
            d["smtp_password"] = "***"
        return d

    @classmethod
    def for_gmail(cls, username: str, password: str, **kwargs: Any) -> MailConfig:
        return cls(smtp_host="smtp.gmail.com", smtp_port=587, smtp_username=username, smtp_password=password, use_tls=True, **kwargs)

    @classmethod
    def for_outlook(cls, username: str, password: str, **kwargs: Any) -> MailConfig:
        return cls(smtp_host="smtp-mail.outlook.com", smtp_port=587, smtp_username=username, smtp_password=password, use_tls=True, **kwargs)

    @classmethod
    def for_sendgrid(cls, api_key: str, **kwargs: Any) -> MailConfig:
        return cls(smtp_host="smtp.sendgrid.net", smtp_port=587, smtp_username="apikey", smtp_password=api_key, use_tls=True, **kwargs)


# ── Models ───────────────────────────────────────────────────────────────────


@dataclass
class EmailAttachment:
    filename: str
    content: Union[bytes, str]
    content_type: Optional[str] = None
    content_id: Optional[str] = None

    def __post_init__(self) -> None:
        if isinstance(self.content, str):
            path = Path(self.content)
            if path.exists():
                self.content = path.read_bytes()
                if not self.content_type:
                    import mimetypes
                    self.content_type, _ = mimetypes.guess_type(str(path))
        if not self.content_type:
            self.content_type = "application/octet-stream"


@dataclass
class EmailMessage:
    to: Union[str, List[str]]
    subject: str
    body: Optional[str] = None
    html_body: Optional[str] = None
    template_name: Optional[str] = None
    template_context: Optional[Dict[str, Any]] = None
    from_email: Optional[str] = None
    reply_to: Optional[Union[str, List[str]]] = None
    cc: Optional[Union[str, List[str]]] = None
    bcc: Optional[Union[str, List[str]]] = None
    attachments: Optional[List[EmailAttachment]] = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    headers: Optional[Dict[str, str]] = None
    priority: Optional[int] = None

    def __post_init__(self) -> None:
        for attr in ("to", "cc", "bcc", "reply_to"):
            val = getattr(self, attr)
            if isinstance(val, str):
                setattr(self, attr, [val])
            elif val is None:
                setattr(self, attr, [])
        if self.attachments is None:
            self.attachments = []
        if self.headers is None:
            self.headers = {}
        if self.template_context is None:
            self.template_context = {}

    def add_attachment(self, filename: str, content: Union[bytes, str], content_type: Optional[str] = None, content_id: Optional[str] = None) -> None:
        self.attachments.append(EmailAttachment(filename=filename, content=content, content_type=content_type, content_id=content_id))

    def add_header(self, name: str, value: str) -> None:
        self.headers[name] = value

    def to_mime_message(self, from_email: Optional[str] = None) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = self.subject
        msg["To"] = ", ".join(self.to)
        msg["From"] = from_email or self.from_email or ""
        msg["Message-ID"] = self.message_id
        if self.cc:
            msg["Cc"] = ", ".join(self.cc)
        if self.reply_to:
            msg["Reply-To"] = ", ".join(self.reply_to)
        if self.priority:
            mapping = {1: "High", 3: "Normal", 5: "Low"}
            msg["X-Priority"] = str(self.priority)
            msg["Priority"] = mapping.get(self.priority, "Normal")
        for name, value in self.headers.items():
            msg[name] = value
        if self.body:
            msg.attach(MIMEText(self.body, "plain", "utf-8"))
        if self.html_body:
            msg.attach(MIMEText(self.html_body, "html", "utf-8"))
        for att in self.attachments:
            part = MIMEBase(*att.content_type.split("/", 1))
            part.set_payload(att.content)
            import email.encoders
            email.encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={att.filename}")
            if att.content_id:
                part.add_header("Content-ID", f"<{att.content_id}>")
            msg.attach(part)
        return msg


@dataclass
class EmailResult:
    success: bool
    message_id: str
    to: List[str]
    subject: str
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"success": self.success, "message_id": self.message_id, "to": self.to, "subject": self.subject, "sent_at": self.sent_at.isoformat(), "error": self.error, "provider_response": self.provider_response}


# ── Client ───────────────────────────────────────────────────────────────────


class MailClient:
    def __init__(self, config: Optional[MailConfig] = None) -> None:
        self.config = config or MailConfig()
        self._smtp: Optional[smtplib.SMTP] = None
        self._template_env: Optional[Any] = None
        self._started = False
        if _JINJA2 and self.config.template_directory:
            self._setup_templates()

    def _setup_templates(self) -> None:
        path = Path(self.config.template_directory)
        if not path.exists():
            logger.warning(f"Template directory not found: {path}")
            return
        self._template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(path)),
            autoescape=self.config.template_auto_escape,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    async def start(self) -> None:
        if self._started or self.config.suppress_send:
            self._started = True
            return
        if self.config.use_ssl:
            self._smtp = smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, timeout=self.config.smtp_timeout)
        else:
            self._smtp = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=self.config.smtp_timeout)
            if self.config.use_tls:
                self._smtp.starttls()
        if self.config.debug:
            self._smtp.set_debuglevel(1)
        if self.config.smtp_username and self.config.smtp_password:
            self._smtp.login(self.config.smtp_username, self.config.smtp_password)
        self._started = True
        logger.info("Mail client started")

    async def stop(self) -> None:
        if not self._started:
            return
        if self._smtp:
            self._smtp.quit()
            self._smtp = None
        self._started = False
        logger.info("Mail client stopped")

    async def send_email(
        self,
        to: Union[str, List[str]],
        subject: str,
        body: Optional[str] = None,
        html_body: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[Union[str, List[str]]] = None,
        cc: Optional[Union[str, List[str]]] = None,
        bcc: Optional[Union[str, List[str]]] = None,
        attachments: Optional[List[Any]] = None,
        template_name: Optional[str] = None,
        template_context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> EmailResult:
        message = EmailMessage(to=to, subject=subject, body=body, html_body=html_body, from_email=from_email, reply_to=reply_to, cc=cc, bcc=bcc, template_name=template_name, template_context=template_context, **kwargs)
        if attachments:
            for att in attachments:
                if isinstance(att, dict):
                    message.add_attachment(**att)
                else:
                    message.add_attachment(att)
        return await self.send_message(message)

    async def send_template_email(self, to: Union[str, List[str]], subject: str, template_name: str, context: Optional[Dict[str, Any]] = None, from_email: Optional[str] = None, **kwargs: Any) -> EmailResult:
        return await self.send_email(to=to, subject=subject, template_name=template_name, template_context=context, from_email=from_email, **kwargs)

    async def send_message(self, message: EmailMessage) -> EmailResult:
        try:
            if message.template_name and self._template_env:
                self._render_template(message)
            from_email = message.from_email or self.config.default_from
            if not from_email:
                raise ValueError("No 'from' email address specified")
            mime_message = message.to_mime_message(from_email)
            if self.config.default_cc and not message.cc:
                mime_message["Cc"] = ", ".join(self.config.default_cc)
                message.cc.extend(self.config.default_cc)
            if self.config.default_bcc and not message.bcc:
                message.bcc.extend(self.config.default_bcc)
            recipients = list(message.to)
            if message.cc:
                recipients.extend(message.cc)
            if message.bcc:
                recipients.extend(message.bcc)
            if self.config.suppress_send:
                logger.info(f"Suppressed: {message.subject} to {recipients}")
                return EmailResult(success=True, message_id=message.message_id, to=recipients, subject=message.subject, provider_response={"suppressed": True})
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_mime, mime_message, recipients)
            logger.info(f"Sent: {message.message_id} to {recipients}")
            return EmailResult(success=True, message_id=message.message_id, to=recipients, subject=message.subject)
        except Exception as e:
            logger.error(f"Failed: {e}")
            return EmailResult(success=False, message_id=message.message_id, to=list(message.to), subject=message.subject, error=str(e))

    def _send_mime(self, mime_message: MIMEMultipart, recipients: List[str]) -> None:
        if not self._smtp:
            raise RuntimeError("SMTP not connected")
        self._smtp.sendmail(mime_message["From"], recipients, mime_message.as_string())

    def _render_template(self, message: EmailMessage) -> None:
        if not self._template_env or not message.template_name:
            return
        try:
            html = self._template_env.get_template(f"{message.template_name}.html")
            message.html_body = html.render(**message.template_context)
            try:
                text = self._template_env.get_template(f"{message.template_name}.txt")
                message.body = text.render(**message.template_context)
            except jinja2.TemplateNotFound:
                pass
        except jinja2.TemplateNotFound as e:
            logger.error(f"Template not found: {e}")
            raise
        except jinja2.TemplateError as e:
            logger.error(f"Template error: {e}")
            raise


# ── Setup ────────────────────────────────────────────────────────────────────


def setup_mail(app, config: Optional[MailConfig] = None) -> MailClient:
    if hasattr(app, "mail_client"):
        return app.mail_client
    client = MailClient(config=config)
    app.mail_client = client
    app.on_startup(client.start)
    app.on_shutdown(client.stop)
    return client


def get_mail_client(request) -> MailClient:
    client = getattr(request.app, "mail_client", None)
    if client is None:
        raise RuntimeError("Mail client not initialized. Call setup_mail(app) during startup.")
    return client
