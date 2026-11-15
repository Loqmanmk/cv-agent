from pathlib import Path

from app.core.config import Settings
from app.domain.mail import EmailSender
from app.infrastructure.outbox_sender import OutboxEmailSender
from app.infrastructure.smtp_sender import Security, SmtpConfig, SmtpEmailSender

SECURITY_MODES: dict[str, Security] = {"starttls": "starttls", "tls": "tls"}


def build_email_sender(settings: Settings) -> EmailSender:
    """The sender chosen by EMAIL_BACKEND: files for development, SMTP for real emails."""
    backend = settings.email_backend.strip().lower()
    if backend == "outbox":
        return OutboxEmailSender(Path(settings.email_outbox_dir))
    if backend == "smtp":
        return SmtpEmailSender(smtp_config(settings))
    raise ValueError("EMAIL_BACKEND must be 'outbox' or 'smtp'.")


def smtp_config(settings: Settings) -> SmtpConfig:
    """The SMTP settings, checked at startup so a mistake is found before the first email."""
    password = settings.smtp_password
    required = {
        "SMTP_HOST": settings.smtp_host,
        "SMTP_USERNAME": settings.smtp_username,
        "SMTP_PASSWORD": "" if password is None else password.get_secret_value(),
        "EMAIL_FROM_ADDRESS": settings.email_from_address,
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing or password is None:
        raise ValueError("EMAIL_BACKEND is 'smtp' but these are empty: " + ", ".join(missing))
    security = SECURITY_MODES.get(settings.smtp_security.strip().lower())
    if security is None:
        raise ValueError("SMTP_SECURITY must be 'starttls' (port 587) or 'tls' (port 465).")
    if "@" not in settings.email_from_address:
        raise ValueError("EMAIL_FROM_ADDRESS must be an email address.")
    return SmtpConfig(
        host=settings.smtp_host.strip(),
        port=settings.smtp_port,
        security=security,
        username=settings.smtp_username.strip(),
        password=password,
        from_address=settings.email_from_address.strip(),
        from_name=settings.email_from_name.strip() or "CV Agent",
    )
