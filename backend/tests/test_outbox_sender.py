from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.domain.mail import EmailMessage
from app.infrastructure.outbox_sender import OutboxEmailSender

MESSAGE = EmailMessage(
    to="jane@example.com",
    subject="Confirm your email",
    text="Open this link: https://example.com/verify?token=abc",
)


def test_each_email_becomes_a_file_with_its_recipient_subject_and_text(tmp_path: Path) -> None:
    clock = lambda: datetime(2026, 11, 11, 12, 0, tzinfo=UTC)  # noqa: E731
    sender = OutboxEmailSender(tmp_path / "outbox", clock)

    sender.send(MESSAGE)
    sender.send(MESSAGE)

    files = sorted((tmp_path / "outbox").iterdir())
    content = files[0].read_text(encoding="utf-8")
    assert len(files) == 2
    assert files[0].name.startswith("20261111T120000-")
    assert content.startswith("To: jane@example.com\nSubject: Confirm your email\n\n")
    assert "token=abc" in content


@pytest.mark.parametrize(
    ("to", "subject"),
    [
        ("jane@example.com\nBcc: victim@example.com", "Hello"),
        ("jane@example.com", "Hello\r\nBcc: victim@example.com"),
    ],
)
def test_a_line_break_in_a_header_is_refused(to: str, subject: str) -> None:
    with pytest.raises(ValueError, match="line break"):
        EmailMessage(to=to, subject=subject, text="body")


def test_the_text_with_its_link_never_appears_in_a_printed_message() -> None:
    assert "token=abc" not in repr(MESSAGE)
