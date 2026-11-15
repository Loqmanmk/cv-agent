import smtplib
import ssl
from email.message import EmailMessage as MimeMessage

import pytest
from pydantic import SecretStr

from app.domain.mail import EmailDeliveryError, EmailMessage
from app.infrastructure.smtp_sender import Security, SmtpConfig, SmtpEmailSender

MESSAGE = EmailMessage(to="jane@example.com", subject="Confirm your email", text="Hello Jane")


def config(security: Security = "starttls") -> SmtpConfig:
    return SmtpConfig(
        host="smtp.example.com",
        port=587 if security == "starttls" else 465,
        security=security,
        username="smtp-user",
        password=SecretStr("smtp-password"),
        from_address="no-reply@cvagent.example",
        from_name="CV Agent",
    )


class FakeServer:
    """Records what the sender asks of the SMTP server."""

    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[str] = []
        self.sent: list[MimeMessage] = []
        self.opened_with: tuple[SmtpConfig, ssl.SSLContext] | None = None

    def connect(self, settings: SmtpConfig, context: ssl.SSLContext) -> "FakeServer":
        self.opened_with = (settings, context)
        return self

    def starttls(self, *, context: ssl.SSLContext) -> object:
        self.calls.append("starttls")
        if self.failure is not None:
            raise self.failure
        return None

    def login(self, user: str, password: str) -> object:
        self.calls.append(f"login {user} {password}")
        return None

    def send_message(self, msg: MimeMessage) -> object:
        self.calls.append("send")
        self.sent.append(msg)
        return {}

    def quit(self) -> object:
        self.calls.append("quit")
        return None

    def close(self) -> None:
        self.calls.append("close")


def test_the_link_is_encrypted_before_the_password_is_sent() -> None:
    server = FakeServer()

    SmtpEmailSender(config(), server.connect).send(MESSAGE)

    assert server.calls == ["starttls", "login smtp-user smtp-password", "send", "quit", "close"]


def test_the_certificate_of_the_provider_is_checked() -> None:
    server = FakeServer()

    SmtpEmailSender(config(), server.connect).send(MESSAGE)

    assert server.opened_with is not None
    context = server.opened_with[1]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_implicit_tls_does_not_ask_for_starttls() -> None:
    server = FakeServer()

    SmtpEmailSender(config("tls"), server.connect).send(MESSAGE)

    assert "starttls" not in server.calls
    assert "send" in server.calls


def test_the_email_has_the_right_headers_and_text() -> None:
    server = FakeServer()

    SmtpEmailSender(config(), server.connect).send(MESSAGE)

    sent = server.sent[0]
    assert sent["From"] == "CV Agent <no-reply@cvagent.example>"
    assert sent["To"] == "jane@example.com"
    assert sent["Subject"] == "Confirm your email"
    assert sent["Auto-Submitted"] == "auto-generated"
    assert sent["Message-ID"].endswith("@cvagent.example>")
    assert sent["Date"]
    assert sent.get_content().strip() == "Hello Jane"


def test_non_latin_text_is_sent_unchanged() -> None:
    server = FakeServer()
    arabic = EmailMessage(to="jane@example.com", subject="تأكيد البريد", text="مرحبا")

    SmtpEmailSender(config(), server.connect).send(arabic)

    assert server.sent[0]["Subject"] == "تأكيد البريد"
    assert server.sent[0].get_content().strip() == "مرحبا"


@pytest.mark.parametrize(
    "failure",
    [
        smtplib.SMTPNotSupportedError("STARTTLS extension not supported by server."),
        smtplib.SMTPRecipientsRefused({"jane@example.com": (550, b"No such user")}),
        TimeoutError("timed out"),
    ],
    ids=["no-encryption", "refused", "timeout"],
)
def test_a_failure_is_reported_without_the_address(failure: Exception) -> None:
    server = FakeServer(failure)

    with pytest.raises(EmailDeliveryError) as caught:
        SmtpEmailSender(config(), server.connect).send(MESSAGE)

    assert "jane@example.com" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert "send" not in server.calls
    assert server.calls[-1] == "close"


def test_the_password_never_appears_in_a_printed_config() -> None:
    assert "smtp-password" not in repr(config())
