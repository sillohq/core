from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any


@dataclass
class EmailAttachment:
    """Emailattachment"""

    filename: str
    content: bytes | str
    content_type: str | None = None
    content_id: str | None = None

    def __post_init__(self) -> None:
        """Post Init"""
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
    """Emailmessage"""

    to: str | list[str]
    subject: str
    body: str | None = None
    html_body: str | None = None
    template_name: str | None = None
    template_context: dict[str, Any] | None = None
    from_email: str | None = None
    reply_to: str | list[str] | None = None
    cc: str | list[str] | None = None
    bcc: str | list[str] | None = None
    attachments: list[EmailAttachment] | None = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    headers: dict[str, str] | None = None
    priority: int | None = None

    def __post_init__(self) -> None:
        """Post Init"""
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

    def add_attachment(
        self,
        filename: str,
        content: bytes | str,
        content_type: str | None = None,
        content_id: str | None = None,
    ) -> None:
        """Add Attachment"""
        self.attachments.append(  # ty: ignore[unresolved-attribute]
            EmailAttachment(
                filename=filename,
                content=content,
                content_type=content_type,
                content_id=content_id,
            )
        )

    def add_header(self, name: str, value: str) -> None:
        """Add Header"""
        self.headers[name] = value  # ty: ignore[invalid-assignment]

    def to_mime_message(self, from_email: str | None = None) -> MIMEMultipart:
        """To Mime Message"""
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
        for name, value in self.headers.items():  # ty: ignore[unresolved-attribute]
            msg[name] = value
        if self.body:
            msg.attach(MIMEText(self.body, "plain", "utf-8"))
        if self.html_body:
            msg.attach(MIMEText(self.html_body, "html", "utf-8"))
        for att in self.attachments:  # ty: ignore[not-iterable]
            part = MIMEBase(*att.content_type.split("/", 1))  # ty: ignore[unresolved-attribute]
            part.set_payload(att.content)
            import email.encoders

            email.encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition", f"attachment; filename={att.filename}"
            )
            if att.content_id:
                part.add_header("Content-ID", f"<{att.content_id}>")
            msg.attach(part)
        return msg


@dataclass
class EmailResult:
    """Emailresult"""

    success: bool
    message_id: str
    to: list[str]
    subject: str
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None
    provider_response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """To Dict"""
        return {
            "success": self.success,
            "message_id": self.message_id,
            "to": self.to,
            "subject": self.subject,
            "sent_at": self.sent_at.isoformat(),
            "error": self.error,
            "provider_response": self.provider_response,
        }
