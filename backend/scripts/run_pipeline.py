import sys
from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.domain.llm import LLMError
from app.infrastructure.application_factory import build_application_service
from app.services.application_service import ApplicationRequest, InvalidApplicationInputError
from app.services.cv_structurer import CVStructuringError
from app.services.cv_tailor import TailoringViolationError
from app.services.job_analyzer import JobAnalysisError
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.letter_guard import LetterViolationError
from app.services.page_fitter import PageOverflowError

OUTPUT = Path("../data/output")
EXPECTED_ERRORS = (
    InvalidApplicationInputError,
    JobAnalysisError,
    CVStructuringError,
    UnsupportedLetterLanguageError,
    LLMError,
    PageOverflowError,
)


def main(cv_path: str, job_path: str) -> None:
    settings = get_settings()
    if not settings.applicant_city:
        sys.exit("APPLICANT_CITY is missing in backend/.env")

    cv_file = Path(cv_path)
    request = ApplicationRequest(
        cv_filename=cv_file.name,
        cv_content=cv_file.read_bytes(),
        job_text=Path(job_path).read_text(encoding="utf-8"),
        address=settings.applicant_address,
        city=settings.applicant_city,
        gender=settings.applicant_gender,
        today=date.today(),
    )

    try:
        result = build_application_service(settings).create(request)
    except (TailoringViolationError, LetterViolationError) as error:
        sys.exit("Rejected by a faithfulness guard:\n- " + "\n- ".join(error.violations))
    except EXPECTED_ERRORS as error:
        sys.exit(f"Failed: {error}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "cv.pdf").write_bytes(result.cv_pdf)
    (OUTPUT / "letter.pdf").write_bytes(result.letter_pdf)
    print(f"Job: {result.offer.title} at {result.offer.company} ({result.offer.language})")
    print(f"Photo used: {result.photo_used}")
    print(f"Saved to {OUTPUT / 'cv.pdf'} and {OUTPUT / 'letter.pdf'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
