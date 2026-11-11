import logging

from app.domain.mail import EmailMessage, EmailSender

logger = logging.getLogger(__name__)


def clean_base_url(url: str) -> str:
    """The address of the website, used to build the links in emails."""
    base = url.strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise ValueError("APP_BASE_URL must start with http:// or https://")
    return base


def send_quietly(sender: EmailSender, message: EmailMessage) -> None:
    """Send, and only log a failure: the reply must not reveal which addresses exist."""
    try:
        sender.send(message)
    except Exception:
        logger.exception("An email could not be sent.")
