import time
from collections.abc import Callable

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, SecretStr, ValidationError

from app.domain.llm import LLMError, LLMProvider

TEMPERATURE = 0.2
MAX_ATTEMPTS = 4
BASE_DELAY_SECONDS = 2.0
RETRYABLE_CODES = {429, 500, 502, 503, 504}


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
    """AI provider backed by the Google Gemini API."""

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
                    self._sleep(BASE_DELAY_SECONDS * 2 ** (attempt - 1))
                    continue
                raise LLMError(f"Gemini request failed (code {exc.code}).") from exc
            except httpx.TransportError as exc:
                raise LLMError("Could not reach Gemini (network error).") from exc
            if not response.text:
                raise LLMError("Gemini returned no content.")
            return str(response.text)
        raise LLMError("Gemini request failed.")
