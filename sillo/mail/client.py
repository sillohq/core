from __future__ import annotations

import asyncio
import logging
import smtplib
from pathlib import Path
from typing import Any

from .config import MailConfig
from .models import EmailMessage, EmailResult

logger = logging.getLogger("sillo.mail")

try:
    import jinja2

    _JINJA2 = True
except ImportError:
    _JINJA2 = False


class MailClient:
    """Mailclient"""

    def __init__(self, config: MailConfig | None = None) -> None:
        """Init"""
        self.config = config or MailConfig()
        self._smtp: smtplib.SMTP | None = None
        self._template_env: Any | None = None
        self._started = False
        if _JINJA2 and self.config.template_directory:
            self._setup_templates()

    def _setup_templates(self) -> None:
        """Setup Templates"""
        path = Path(self.config.template_directory)  # ty: ignore[invalid-argument-type]
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
        """Start"""
        if self._started or self.config.suppress_send:
            self._started = True
            return
        await self._connect()
        self._started = True
        logger.info("Mail client started")

    async def stop(self) -> None:
        """Stop"""
        if not self._started:
            return
        if self._smtp:
            try:
                self._smtp.quit()
            except Exception:
                pass
            self._smtp = None
        self._started = False
        logger.info("Mail client stopped")

    async def _connect(self) -> None:
        """Connect"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._connect_sync)

    def _connect_sync(self) -> None:
        """Connect Sync"""
        if self.config.use_ssl:
            self._smtp = smtplib.SMTP_SSL(
                self.config.smtp_host,
                self.config.smtp_port,
                timeout=self.config.smtp_timeout,
            )
        else:
            self._smtp = smtplib.SMTP(
                self.config.smtp_host,
                self.config.smtp_port,
                timeout=self.config.smtp_timeout,
            )
            if self.config.use_tls:
                self._smtp.starttls()
        if self.config.debug:
            self._smtp.set_debuglevel(1)
        if self.config.smtp_username and self.config.smtp_password:
            self._smtp.login(self.config.smtp_username, self.config.smtp_password)

    async def _ensure_connected(self) -> None:
        """Ensure Connected"""
        if self.config.suppress_send:
            return
        if self._smtp is None:
            await self._connect()
            return
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._smtp.noop)
        except Exception:
            logger.debug("SMTP connection lost, reconnecting...")
            self._smtp = None
            await self._connect()

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str | None = None,
        html_body: str | None = None,
        from_email: str | None = None,
        reply_to: str | list[str] | None = None,
        cc: str | list[str] | None = None,
        bcc: str | list[str] | None = None,
        attachments: list[Any] | None = None,
        template_name: str | None = None,
        template_context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> EmailResult:
        """Send Email"""
        message = EmailMessage(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            from_email=from_email,
            reply_to=reply_to,
            cc=cc,
            bcc=bcc,
            template_name=template_name,
            template_context=template_context,
            **kwargs,
        )
        if attachments:
            for att in attachments:
                if isinstance(att, dict):
                    message.add_attachment(**att)
                else:
                    message.add_attachment(att)  # ty: ignore[missing-argument]
        return await self.send_message(message)

    async def send_template_email(
        self,
        to: str | list[str],
        subject: str,
        template_name: str,
        context: dict[str, Any] | None = None,
        from_email: str | None = None,
        **kwargs: Any,
    ) -> EmailResult:
        """Send Template Email"""
        return await self.send_email(
            to=to,
            subject=subject,
            template_name=template_name,
            template_context=context,
            from_email=from_email,
            **kwargs,
        )

    async def send_message(self, message: EmailMessage) -> EmailResult:
        """Send Message"""
        try:
            if message.template_name and self._template_env:
                self._render_template(message)
            from_email = message.from_email or self.config.default_from
            if not from_email:
                raise ValueError("No 'from' email address specified")
            mime_message = message.to_mime_message(from_email)
            if self.config.default_cc and not message.cc:
                mime_message["Cc"] = ", ".join(self.config.default_cc)
                message.cc.extend(self.config.default_cc)  # ty: ignore[unresolved-attribute]
            if self.config.default_bcc and not message.bcc:
                message.bcc.extend(self.config.default_bcc)  # ty: ignore[unresolved-attribute]
            recipients = list(message.to)
            if message.cc:
                recipients.extend(message.cc)
            if message.bcc:
                recipients.extend(message.bcc)
            if self.config.suppress_send:
                logger.info(f"Suppressed: {message.subject} to {recipients}")
                return EmailResult(
                    success=True,
                    message_id=message.message_id,
                    to=recipients,
                    subject=message.subject,
                    provider_response={"suppressed": True},
                )

            await self._ensure_connected()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_mime, mime_message, recipients)
            logger.info(f"Sent: {message.message_id} to {recipients}")
            return EmailResult(
                success=True,
                message_id=message.message_id,
                to=recipients,
                subject=message.subject,
            )
        except Exception as e:
            logger.error(f"Failed: {e}")
            return EmailResult(
                success=False,
                message_id=message.message_id,
                to=list(message.to),
                subject=message.subject,
                error=str(e),
            )

    def _send_mime(self, mime_message, recipients: list[str]) -> None:
        """Send Mime"""
        if not self._smtp:
            raise RuntimeError("SMTP not connected")
        self._smtp.sendmail(mime_message["From"], recipients, mime_message.as_string())

    def _render_template(self, message: EmailMessage) -> None:
        """Render Template"""
        if not self._template_env or not message.template_name:
            return
        try:
            html = self._template_env.get_template(f"{message.template_name}.html")
            message.html_body = html.render(**message.template_context)  # ty: ignore[invalid-argument-type]
            try:
                text = self._template_env.get_template(f"{message.template_name}.txt")
                message.body = text.render(**message.template_context)  # ty: ignore[invalid-argument-type]
            except jinja2.TemplateNotFound:
                pass
        except jinja2.TemplateNotFound as e:
            logger.error(f"Template not found: {e}")
            raise
        except jinja2.TemplateError as e:
            logger.error(f"Template error: {e}")
            raise


def setup_mail(app, config: MailConfig | None = None) -> MailClient:
    """Setup Mail"""
    if "mail_client" in app.state:
        return app.state["mail_client"]
    client = MailClient(config=config)
    app.state["mail_client"] = client
    app.on_startup(client.start)
    app.on_shutdown(client.stop)
    return client


def get_mail_client(request) -> MailClient:
    """Get Mail Client"""
    client = request.state._state.get("mail_client")
    if client is None:
        raise RuntimeError(
            "Mail client not initialized. Call setup_mail(app) during startup."
        )
    return client
