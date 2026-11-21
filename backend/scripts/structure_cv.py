import sys
from pathlib import Path

from app.core.config import get_settings
from app.domain.llm import LLMError
from app.infrastructure.docx_parser import DocxParser
from app.infrastructure.llm_factory import build_llm_chain
from app.services.cv_structurer import CVStructurer, CVStructuringError
from app.services.masking_llm_provider import MaskingLLMProvider

OUTPUT = Path("../data/extracted/cv.json")


def main(path: str) -> None:
    settings = get_settings()
    if settings.gemini_api_key is None:
        sys.exit("GEMINI_API_KEY is missing in backend/.env")

    gemini = build_llm_chain(settings)
    structurer = CVStructurer(MaskingLLMProvider(gemini))
    parsed = DocxParser().parse(Path(path).read_bytes())

    try:
        cv = structurer.structure(parsed.text)
    except (LLMError, CVStructuringError) as error:
        sys.exit(f"Failed: {error}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(cv.model_dump_json(indent=2), encoding="utf-8")

    print(f"Saved to {OUTPUT}")
    print(f"experiences:    {len(cv.experiences)}")
    print(f"projects:       {len(cv.projects)}")
    print(f"education:      {len(cv.education)}")
    print(f"skill groups:   {len(cv.skills)}")
    print(f"certifications: {len(cv.certifications)}")
    print(f"languages:      {len(cv.languages)}")


if __name__ == "__main__":
    main(sys.argv[1])
