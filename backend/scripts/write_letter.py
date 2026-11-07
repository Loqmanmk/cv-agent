import sys
from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.domain.cv import CV
from app.domain.job import JobOffer
from app.domain.letter import LetterSender
from app.domain.llm import LLMError
from app.infrastructure.llm_factory import build_gemini_chain
from app.services.letter_assembler import LetterAssembler
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.letter_guard import LetterViolationError
from app.services.letter_writer import LetterWriter
from app.services.masking_llm_provider import MaskingLLMProvider

DATA = Path("../data/extracted")
LANGUAGES = ("fr", "de", "en", "ar")


def main(language: str | None) -> None:
    if language is not None and language not in LANGUAGES:
        sys.exit(f"Language must be one of: {', '.join(LANGUAGES)}")
    settings = get_settings()
    if not settings.applicant_city:
        sys.exit("APPLICANT_CITY is missing in backend/.env")

    cv = CV.model_validate_json((DATA / "tailored_cv.json").read_text(encoding="utf-8"))
    offer = JobOffer.model_validate_json((DATA / "job.json").read_text(encoding="utf-8"))
    if language is not None:
        offer = offer.model_copy(update={"language": language})
    sender = LetterSender(
        name=cv.header.name,
        email=cv.header.email,
        phone=cv.header.phone,
        address=settings.applicant_address,
        city=settings.applicant_city,
        gender=settings.applicant_gender,
    )

    try:
        writer = LetterWriter(MaskingLLMProvider(build_gemini_chain(settings)))
        body = writer.write(cv, offer, sender.gender)
    except LetterViolationError as error:
        sys.exit("Rejected by the letter guard:\n- " + "\n- ".join(error.violations))
    except (LLMError, UnsupportedLetterLanguageError) as error:
        sys.exit(f"Failed: {error}")

    letter = LetterAssembler().assemble(body, offer, sender, date.today())
    target = DATA / f"letter_{offer.language}.json"
    target.write_text(letter.model_dump_json(indent=2), encoding="utf-8")

    print(f"Saved to {target}\n")
    print(f"{letter.place_date}\n\n{letter.subject}\n\n{letter.greeting}\n")
    print("\n\n".join(letter.paragraphs))
    print(f"\n{letter.signature}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
