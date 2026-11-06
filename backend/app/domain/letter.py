from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from app.domain.cv import DomainModel

Gender = Literal["m", "f"]


class LetterBody(DomainModel):
    """The three paragraphs written by the AI."""

    opening: str
    experience: str
    motivation: str


@dataclass(frozen=True)
class LetterSender:
    """Who sends the letter. Never given to the AI."""

    name: str
    email: str
    phone: str
    address: str
    city: str
    gender: Gender


class SenderBlock(DomainModel):
    name: str
    address: str
    email: str
    phone: str


class RecipientBlock(DomainModel):
    contact: str = ""
    company: str = ""
    address: str = ""


class CoverLetter(DomainModel):
    sender: SenderBlock
    recipient: RecipientBlock
    place_date: str
    subject: str
    greeting: str
    paragraphs: list[str] = Field(default_factory=list)
    signature: str
