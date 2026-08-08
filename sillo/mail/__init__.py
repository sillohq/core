from .client import MailClient, get_mail_client, setup_mail
from .config import MailConfig
from .models import EmailAttachment, EmailMessage, EmailResult

__all__ = [
    "EmailAttachment",
    "EmailMessage",
    "EmailResult",
    "MailClient",
    "MailConfig",
    "get_mail_client",
    "setup_mail",
]
