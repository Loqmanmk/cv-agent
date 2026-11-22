import logging
import time
from collections.abc import Callable, Sequence

from pydantic import BaseModel

from app.domain.llm import LLMProvider, LLMUnavailableError

logger = logging.getLogger(__name__)

# An overloaded model is skipped for a few minutes, so the next steps of the same
# application go straight to a model that answers instead of waiting on the busy one again.
DEFAULT_COOLDOWN_SECONDS = 300.0


class FallbackLLMProvider(LLMProvider):
    """Tries providers in order. A provider that is unavailable is skipped until it recovers.

    The provider that answered last is tried first, so once a busy model was left, the
    next calls go straight to the one that works instead of failing on the busy one again.
    """

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
        self._last_good = 0

    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        failures: list[str] = []
        skipped = 0
        for index in self._order():
            if self._cooldown_until.get(index, 0.0) > self._clock():
                skipped += 1
                continue
            try:
                answer = self._providers[index].generate(system_prompt, user_prompt, response_model)
            except LLMUnavailableError as exc:
                delay = exc.retry_after_seconds or DEFAULT_COOLDOWN_SECONDS
                self._cooldown_until[index] = self._clock() + delay
                logger.warning("provider unavailable, trying the next one: %s", exc)
                failures.append(str(exc))
                continue
            self._last_good = index
            return answer
        raise self._all_unavailable(failures, skipped)

    def _order(self) -> list[int]:
        """The provider that answered last, then all the others in their usual order."""
        first = self._last_good
        return [first, *(index for index in range(len(self._providers)) if index != first)]

    def _all_unavailable(self, failures: list[str], skipped: int) -> LLMUnavailableError:
        now = self._clock()
        waits = [until - now for until in self._cooldown_until.values() if until > now]
        parts = list(failures)
        if skipped:
            parts.append(f"{skipped} provider(s) skipped while waiting for their quota to reset")
        message = "All providers are unavailable: " + " | ".join(parts)
        return LLMUnavailableError(message, min(waits, default=None))
