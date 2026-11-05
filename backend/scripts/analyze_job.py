import sys
from pathlib import Path

from app.core.config import get_settings
from app.domain.llm import LLMError
from app.infrastructure.llm_factory import build_gemini_chain
from app.services.job_analyzer import JobAnalysisError, JobAnalyzer

OUTPUT = Path("../data/extracted/job.json")


def main(path: str) -> None:
    settings = get_settings()
    if settings.gemini_api_key is None:
        sys.exit("GEMINI_API_KEY is missing in backend/.env")

    analyzer = JobAnalyzer(build_gemini_chain(settings))
    try:
        offer = analyzer.analyze(Path(path).read_text(encoding="utf-8"))
    except (LLMError, JobAnalysisError) as error:
        sys.exit(f"Failed: {error}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(offer.model_dump_json(indent=2), encoding="utf-8")

    print(f"Saved to {OUTPUT}\n")
    print(f"title:         {offer.title}")
    print(f"company:       {offer.company}")
    print(f"location:      {offer.location}")
    print(f"language:      {offer.language}")
    print(f"contract:      {offer.contract_type}")
    print(f"required:      {offer.required_skills}")
    print(f"nice to have:  {offer.nice_to_have_skills}")
    print(f"keywords:      {offer.keywords}")
    print(f"missions:      {len(offer.missions)}")


if __name__ == "__main__":
    main(sys.argv[1])
