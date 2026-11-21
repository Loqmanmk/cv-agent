import sys
from pathlib import Path

from app.core.config import get_settings
from app.domain.cv import CV
from app.domain.llm import LLMError
from app.infrastructure.llm_factory import build_llm_chain
from app.services.cv_translator import CVTranslator
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.masking_llm_provider import MaskingLLMProvider
from app.services.translation_guard import TranslationViolationError

DATA = Path("../data/extracted")
LANGUAGES = ("de", "en", "ar", "fr")


def main(language: str) -> None:
    if language not in LANGUAGES:
        sys.exit(f"Language must be one of: {', '.join(LANGUAGES)}")
    settings = get_settings()
    cv = CV.model_validate_json((DATA / "tailored_cv.json").read_text(encoding="utf-8"))
    translator = CVTranslator(MaskingLLMProvider(build_llm_chain(settings)))

    try:
        translated = translator.translate(cv, language)
    except TranslationViolationError as error:
        sys.exit("Rejected by the translation guard:\n- " + "\n- ".join(error.violations))
    except (LLMError, UnsupportedLetterLanguageError) as error:
        sys.exit(f"Failed: {error}")

    target = DATA / f"tailored_cv_{language}.json"
    target.write_text(translated.model_dump_json(indent=2), encoding="utf-8")
    print(f"Saved to {target}\n")
    print("HEADLINE:   ", translated.header.headline)
    print("TARGET LINE:", translated.header.target_line)
    print("LOCATION:   ", translated.header.location)
    print("\nPROFILE:\n", translated.profile)


if __name__ == "__main__":
    main(sys.argv[1])
