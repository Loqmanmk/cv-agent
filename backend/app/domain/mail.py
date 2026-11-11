from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str = field(repr=False)

    def __post_init__(self) -> None:
        # A line break in a header could add hidden recipients or headers to the email.
        for name, value in (("recipient", self.to), ("subject", self.subject)):
            if "\r" in value or "\n" in value:
                raise ValueError(f"The {name} of an email cannot contain a line break.")


class EmailSender(ABC):
    """Contract for anything that delivers an email."""

    @abstractmethod
    def send(self, message: EmailMessage) -> None: ...
