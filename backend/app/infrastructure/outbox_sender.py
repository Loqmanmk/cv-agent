import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app.domain.mail import EmailMessage, EmailSender


def _utc_now() -> datetime:
    return datetime.now(UTC)


class OutboxEmailSender(EmailSender):
    """DEVELOPMENT ONLY: writes each email to a file instead of sending it.

    The files contain live links, so the folder must never be shared or used in production.
    """

    def __init__(self, directory: Path, clock: Callable[[], datetime] = _utc_now) -> None:
        self._directory = directory
        self._clock = clock

    def send(self, message: EmailMessage) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        stamp = self._clock().strftime("%Y%m%dT%H%M%S")
        path = self._directory / f"{stamp}-{uuid.uuid4().hex[:8]}.txt"
        content = f"To: {message.to}\nSubject: {message.subject}\n\n{message.text}\n"
        path.write_text(content, encoding="utf-8")
