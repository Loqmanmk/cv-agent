from datetime import date

from app.domain.job import JobOffer
from app.domain.letter import (
    CoverLetter,
    LetterBody,
    LetterSender,
    RecipientBlock,
    SenderBlock,
)
from app.services.letter_conventions import LetterConventions, conventions_for


class LetterAssembler:
    """Builds the complete letter around the paragraphs written by the AI."""

    def assemble(
        self,
        body: LetterBody,
        offer: JobOffer,
        sender: LetterSender,
        on: date,
    ) -> CoverLetter:
        conventions = conventions_for(offer.language)
        return CoverLetter(
            sender=SenderBlock(
                name=sender.name,
                address=sender.address,
                email=sender.email,
                phone=sender.phone,
            ),
            recipient=RecipientBlock(
                contact=offer.contact_person,
                company=offer.company,
                address=offer.company_address,
            ),
            place_date=self._place_date(conventions, sender.city, on),
            subject=self._subject(conventions, offer),
            greeting=conventions.greeting,
            paragraphs=[
                body.opening,
                body.experience,
                body.motivation,
                conventions.closing[sender.gender],
            ],
            signature=sender.name,
        )

    @staticmethod
    def _place_date(conventions: LetterConventions, city: str, on: date) -> str:
        day = conventions.first_day if on.day == 1 and conventions.first_day else str(on.day)
        return conventions.place_date.format(
            city=city,
            day=day,
            month=conventions.months[on.month - 1],
            year=on.year,
        )

    @staticmethod
    def _subject(conventions: LetterConventions, offer: JobOffer) -> str:
        if offer.reference:
            return conventions.subject_with_reference.format(
                title=offer.title, reference=offer.reference
            )
        return conventions.subject.format(title=offer.title)
