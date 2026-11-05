from app.core.config import Settings
from app.domain.llm import LLMError, LLMProvider
from app.infrastructure.fallback_llm_provider import FallbackLLMProvider
from app.infrastructure.gemini_provider import GeminiProvider


def build_gemini_chain(settings: Settings) -> LLMProvider:
    """Build a provider that tries each configured Gemini model in order."""
    if settings.gemini_api_key is None:
        raise LLMError("GEMINI_API_KEY is missing.")
    return FallbackLLMProvider(
        [GeminiProvider(settings.gemini_api_key, model) for model in settings.gemini_model_chain]
    )
