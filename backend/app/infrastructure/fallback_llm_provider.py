import logging
import time
from collections.abc import Callable, Sequence

from pydantic import BaseModel

from app.domain.llm import LLMProvider, LLMUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_SECONDS = 30.0


class FallbackLLMProvider(LLMProvider):
    """Tries providers in order. A provider that is unavailable is skipped until it recovers."""

    def __init__(
        self,
        providers: Sequence[LLMProvider],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not providers:
            raise ValueError("At least one provider is required.")
        self._providers = list(providers)
        self._clock = clock
        self._cooldown_until: dict[int, float] = {}

    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        failures: list[str] = []
        skipped = 0
        for index, provider in enumerate(self._providers):
            if self._cooldown_until.get(index, 0.0) > self._clock():
                skipped += 1
                continue
            try:
                return provider.generate(system_prompt, user_prompt, response_model)
            except LLMUnavailableError as exc:
                delay = exc.retry_after_seconds or DEFAULT_COOLDOWN_SECONDS
                self._cooldown_until[index] = self._clock() + delay
                logger.warning("provider unavailable, trying the next one: %s", exc)
                failures.append(str(exc))
        raise self._all_unavailable(failures, skipped)

    def _all_unavailable(self, failures: list[str], skipped: int) -> LLMUnavailableError:
        now = self._clock()
        waits = [until - now for until in self._cooldown_until.values() if until > now]
        parts = list(failures)
        if skipped:
            parts.append(f"{skipped} provider(s) skipped while waiting for their quota to reset")
        message = "All providers are unavailable: " + " | ".join(parts)
        return LLMUnavailableError(message, min(waits, default=None))
