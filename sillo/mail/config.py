from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MailConfig:
    """Mailconfig"""

    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "localhost"))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_username: str | None = field(
        default_factory=lambda: os.getenv("SMTP_USERNAME")
    )
    smtp_password: str | None = field(
        default_factory=lambda: os.getenv("SMTP_PASSWORD")
    )
    use_tls: bool = field(
        default_factory=lambda: os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    )
    use_ssl: bool = field(
        default_factory=lambda: os.getenv("SMTP_USE_SSL", "false").lower() == "true"
    )
    default_from: str | None = field(
        default_factory=lambda: os.getenv("MAIL_DEFAULT_FROM")
    )
    default_reply_to: str | None = field(
        default_factory=lambda: os.getenv("MAIL_DEFAULT_REPLY_TO")
    )
    default_cc: list[str] | None = None
    default_bcc: list[str] | None = None
    smtp_timeout: float = field(
        default_factory=lambda: float(os.getenv("SMTP_TIMEOUT", "30"))
    )
    max_connections: int = field(
        default_factory=lambda: int(os.getenv("SMTP_MAX_CONNECTIONS", "10"))
    )
    template_directory: str | None = field(
        default_factory=lambda: os.getenv("MAIL_TEMPLATE_DIR")
    )
    template_auto_escape: bool = True
    debug: bool = field(
        default_factory=lambda: os.getenv("MAIL_DEBUG", "false").lower() == "true"
    )
    suppress_send: bool = field(
        default_factory=lambda: (
            os.getenv("MAIL_SUPPRESS_SEND", "false").lower() == "true"
        )
    )

    def __post_init__(self) -> None:
        """Post Init"""
        if self.use_ssl and self.use_tls:
            raise ValueError("Cannot use both SSL and TLS")
        if self.smtp_port == 465 and not self.use_ssl:
            self.use_ssl, self.use_tls = True, False
        elif self.smtp_port == 587 and not self.use_tls:
            self.use_tls, self.use_ssl = True, False

    def to_dict(self) -> dict[str, Any]:
        """To Dict"""
        d = {k: v for k, v in self.__dict__.items()}
        if d.get("smtp_password"):
            d["smtp_password"] = "***"
        return d

    @classmethod
    def for_gmail(cls, username: str, password: str, **kwargs: Any) -> MailConfig:
        """For Gmail"""
        return cls(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username=username,
            smtp_password=password,
            use_tls=True,
            **kwargs,
        )

    @classmethod
    def for_outlook(cls, username: str, password: str, **kwargs: Any) -> MailConfig:
        """For Outlook"""
        return cls(
            smtp_host="smtp-mail.outlook.com",
            smtp_port=587,
            smtp_username=username,
            smtp_password=password,
            use_tls=True,
            **kwargs,
        )

    @classmethod
    def for_sendgrid(cls, api_key: str, **kwargs: Any) -> MailConfig:
        """For Sendgrid"""
        return cls(
            smtp_host="smtp.sendgrid.net",
            smtp_port=587,
            smtp_username="apikey",
            smtp_password=api_key,
            use_tls=True,
            **kwargs,
        )
