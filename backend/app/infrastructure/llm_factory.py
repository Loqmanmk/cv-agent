from app.core.config import Settings
from app.domain.llm import LLMError, LLMProvider
from app.infrastructure.fallback_llm_provider import FallbackLLMProvider
from app.infrastructure.gemini_provider import GeminiProvider
from app.infrastructure.groq_provider import GroqProvider


def build_llm_chain(settings: Settings) -> LLMProvider:
    """Every configured model in order: the Gemini models first, then the Groq models.

    A model that is out of quota or overloaded is skipped, so when Google is busy the
    application continues on Groq within seconds.
    """
    providers: list[LLMProvider] = []
    if settings.gemini_api_key is not None and settings.gemini_api_key.get_secret_value():
        key = settings.gemini_api_key
        providers += [GeminiProvider(key, model) for model in settings.gemini_model_chain]
    if settings.groq_api_key is not None and settings.groq_api_key.get_secret_value():
        key = settings.groq_api_key
        providers += [GroqProvider(key, model) for model in settings.groq_model_list]
    if not providers:
        raise LLMError("No AI provider is configured: set GEMINI_API_KEY or GROQ_API_KEY.")
    return FallbackLLMProvider(providers)
