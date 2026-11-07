import logging
from collections.abc import Sequence

from pydantic import BaseModel

from app.domain.llm import LLMProvider, LLMUnavailableError

logger = logging.getLogger(__name__)


class FallbackLLMProvider(LLMProvider):
    """Tries providers in order and moves on when one is unavailable."""

    def __init__(self, providers: Sequence[LLMProvider]) -> None:
        if not providers:
            raise ValueError("At least one provider is required.")
        self._providers = list(providers)

    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        failures: list[str] = []
        for provider in self._providers:
            try:
                return provider.generate(system_prompt, user_prompt, response_model)
            except LLMUnavailableError as exc:
                logger.warning("provider unavailable, trying the next one: %s", exc)
                failures.append(str(exc))
        raise LLMUnavailableError("All providers are unavailable: " + " | ".join(failures))
