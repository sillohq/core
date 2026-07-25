from .config import MailConfig
from .models import EmailAttachment, EmailMessage, EmailResult
from .client import MailClient, setup_mail, get_mail_client

__all__ = [
    "MailConfig",
    "MailClient",
    "EmailMessage",
    "EmailAttachment",
    "EmailResult",
    "setup_mail",
    "get_mail_client",
]
