import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Literal, Protocol

from pydantic import SecretStr

from app.domain.mail import EmailDeliveryError, EmailMessage, EmailSender

Security = Literal["starttls", "tls"]
TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    security: Security
    username: str
    password: SecretStr = field(repr=False)
    from_address: str
    from_name: str


class SmtpConnection(Protocol):
    """The part of smtplib.SMTP that we use, so tests can use a fake server."""

    def starttls(self, *, context: ssl.SSLContext) -> object: ...

    def login(self, user: str, password: str) -> object: ...

    def send_message(self, msg: MimeMessage) -> object: ...

    def quit(self) -> object: ...

    def close(self) -> None: ...


Connector = Callable[[SmtpConfig, ssl.SSLContext], SmtpConnection]


def open_connection(config: SmtpConfig, context: ssl.SSLContext) -> SmtpConnection:
    if config.security == "tls":
        return smtplib.SMTP_SSL(config.host, config.port, timeout=TIMEOUT_SECONDS, context=context)
    return smtplib.SMTP(config.host, config.port, timeout=TIMEOUT_SECONDS)


class SmtpEmailSender(EmailSender):
    """Sends through any SMTP provider (Brevo, Resend, ...), always over an encrypted link.

    The provider's certificate is checked, and a server that cannot encrypt is refused instead
    of being used in clear text.
    """

    def __init__(self, config: SmtpConfig, connect: Connector = open_connection) -> None:
        self._config = config
        self._connect = connect
        self._tls = ssl.create_default_context()

    def send(self, message: EmailMessage) -> None:
        mime = self._build(message)
        try:
            connection = self._connect(self._config, self._tls)
            try:
                if self._config.security == "starttls":
                    connection.starttls(context=self._tls)
                connection.login(self._config.username, self._config.password.get_secret_value())
                connection.send_message(mime)
                connection.quit()
            finally:
                connection.close()
        except (smtplib.SMTPException, OSError) as exc:
            # The provider's reply can quote the recipient: keep it out of the logs.
            raise EmailDeliveryError(f"The email was not sent ({type(exc).__name__}).") from None

    def _build(self, message: EmailMessage) -> MimeMessage:
        sender_domain = self._config.from_address.rpartition("@")[2]
        mime = MimeMessage()
        mime["From"] = formataddr((self._config.from_name, self._config.from_address))
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime["Date"] = formatdate(usegmt=True)
        mime["Message-ID"] = make_msgid(domain=sender_domain)
        # Tells mail servers not to answer with out-of-office replies.
        mime["Auto-Submitted"] = "auto-generated"
        mime.set_content(message.text)
        return mime
