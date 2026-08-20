from .client import MailClient, get_mail_client, send_email, setup_mail
from .config import MailConfig
from .context import NotConfiguredError, current_mail
from .models import EmailAttachment, EmailMessage, EmailResult

__all__ = [
    "EmailAttachment",
    "EmailMessage",
    "EmailResult",
    "MailClient",
    "MailConfig",
    "NotConfiguredError",
    "current_mail",
    "get_mail_client",
    "send_email",
    "setup_mail",
]
