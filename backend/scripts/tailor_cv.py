import sys
from pathlib import Path

from app.core.config import get_settings
from app.domain.cv import CV
from app.domain.job import JobOffer
from app.domain.llm import LLMError
from app.infrastructure.llm_factory import build_gemini_chain
from app.services.cv_tailor import CVTailor
from app.services.masking_llm_provider import MaskingLLMProvider
from app.services.tailoring_guard import TailoringViolationError

DATA = Path("../data/extracted")


def main() -> None:
    settings = get_settings()
    if settings.gemini_api_key is None:
        sys.exit("GEMINI_API_KEY is missing in backend/.env")

    cv = CV.model_validate_json((DATA / "cv.json").read_text(encoding="utf-8"))
    offer = JobOffer.model_validate_json((DATA / "job.json").read_text(encoding="utf-8"))

    gemini = build_gemini_chain(settings)
    tailor = CVTailor(MaskingLLMProvider(gemini))

    try:
        tailored = tailor.tailor(cv, offer)
    except TailoringViolationError as error:
        sys.exit("Rejected by the faithfulness guard:\n- " + "\n- ".join(error.violations))
    except LLMError as error:
        sys.exit(f"Failed: {error}")

    (DATA / "tailored_cv.json").write_text(tailored.model_dump_json(indent=2), encoding="utf-8")

    print(f"Saved to {DATA / 'tailored_cv.json'}\n")
    print("HEADLINE:   ", tailored.header.headline)
    print("TARGET LINE:", tailored.header.target_line)
    print("\nPROFILE:\n", tailored.profile)
    print("\nPROJECTS KEPT:", [project.title for project in tailored.projects])
    print("\nSKILLS:")
    for group in tailored.skills:
        print(f"  {group.category}: {', '.join(group.items)}")


if __name__ == "__main__":
    main()
