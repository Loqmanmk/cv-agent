import logging
import time
from collections.abc import Callable

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, SecretStr, ValidationError

from app.domain.llm import LLMError, LLMProvider, LLMUnavailableError

logger = logging.getLogger(__name__)

TEMPERATURE = 0.2
MAX_ATTEMPTS = 4
BASE_DELAY_SECONDS = 2.0
RETRYABLE_CODES = {500, 502, 503, 504}
UNAVAILABLE_CODES = RETRYABLE_CODES | {429}
MAX_DETAIL_CHARS = 200


def _strip_additional_properties(node: object) -> object:
    """Gemini rejects 'additionalProperties'. Our own validation still enforces it."""
    if isinstance(node, dict):
        return {
            key: _strip_additional_properties(value)
            for key, value in node.items()
            if key != "additionalProperties"
        }
    if isinstance(node, list):
        return [_strip_additional_properties(item) for item in node]
    return node


class GeminiProvider(LLMProvider):
    """AI provider backed by one Gemini model."""

    def __init__(
        self,
        api_key: SecretStr,
        model: str,
        client: genai.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._model = model
        self._client = client or genai.Client(api_key=api_key.get_secret_value())
        self._sleep = sleep

    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_json_schema=_strip_additional_properties(response_model.model_json_schema()),
            temperature=TEMPERATURE,
        )
        text = self._request(user_prompt, config)
        try:
            return response_model.model_validate_json(text)
        except ValidationError as exc:
            raise LLMError("Gemini returned data with an unexpected structure.") from exc

    def _request(self, prompt: str, config: types.GenerateContentConfig) -> str:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model, contents=prompt, config=config
                )
            except errors.APIError as exc:
                if exc.code in RETRYABLE_CODES and attempt < MAX_ATTEMPTS:
                    logger.warning("%s: code %s, retry %s", self._model, exc.code, attempt)
                    self._sleep(BASE_DELAY_SECONDS * 2 ** (attempt - 1))
                    continue
                raise self._to_llm_error(exc) from exc
            except httpx.TransportError as exc:
                raise LLMUnavailableError(f"Gemini {self._model}: network error.") from exc
            if not response.text:
                raise LLMError("Gemini returned no content.")
            return str(response.text)
        raise LLMError("Gemini request failed.")

    def _to_llm_error(self, exc: errors.APIError) -> LLMError:
        if exc.code in UNAVAILABLE_CODES:
            detail = (exc.message or "")[:MAX_DETAIL_CHARS]
            message = f"Gemini {self._model} unavailable (code {exc.code}): {detail}"
            return LLMUnavailableError(message)
        return LLMError(f"Gemini request failed (code {exc.code}).")
