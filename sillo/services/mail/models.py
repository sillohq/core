from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class EmailAttachment:
    """Emailattachment

        Returns:
            [description]

        Raises:
            [description]
    """
    filename: str
    content: Union[bytes, str]
    content_type: Optional[str] = None
    content_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Post Init

            Returns:
                [description]

            Raises:
                [description]
        """
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
    """Emailmessage

        Returns:
            [description]

        Raises:
            [description]
    """
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
        """Post Init

            Returns:
                [description]

            Raises:
                [description]
        """
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
        content: Union[bytes, str],
        content_type: Optional[str] = None,
        content_id: Optional[str] = None,
    ) -> None:
        """Add Attachment

            Args:
                filename: [description]
                content: [description]
                content_type: [description]
                content_id: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        self.attachments.append(
            EmailAttachment(
                filename=filename,
                content=content,
                content_type=content_type,
                content_id=content_id,
            )
        )

    def add_header(self, name: str, value: str) -> None:
        """Add Header

            Args:
                name: [description]
                value: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        self.headers[name] = value

    def to_mime_message(self, from_email: Optional[str] = None) -> MIMEMultipart:
        """To Mime Message

            Args:
                from_email: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
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
            part.add_header(
                "Content-Disposition", f"attachment; filename={att.filename}"
            )
            if att.content_id:
                part.add_header("Content-ID", f"<{att.content_id}>")
            msg.attach(part)
        return msg


@dataclass
class EmailResult:
    """Emailresult

        Returns:
            [description]

        Raises:
            [description]
    """
    success: bool
    message_id: str
    to: List[str]
    subject: str
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """To Dict

            Returns:
                [description]

            Raises:
                [description]
        """
        return {
            "success": self.success,
            "message_id": self.message_id,
            "to": self.to,
            "subject": self.subject,
            "sent_at": self.sent_at.isoformat(),
            "error": self.error,
            "provider_response": self.provider_response,
        }
