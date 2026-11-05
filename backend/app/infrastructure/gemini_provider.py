from google import genai
from google.genai import errors, types
from pydantic import BaseModel, SecretStr, ValidationError

from app.domain.llm import LLMError, LLMProvider

TEMPERATURE = 0.2


class GeminiProvider(LLMProvider):
    """AI provider backed by the Google Gemini API."""

    def __init__(
        self,
        api_key: SecretStr,
        model: str,
        client: genai.Client | None = None,
    ) -> None:
        self._model = model
        self._client = client or genai.Client(api_key=api_key.get_secret_value())

    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=response_model,
            temperature=TEMPERATURE,
        )
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config=config,
            )
        except errors.APIError as exc:
            raise LLMError(f"Gemini request failed (code {exc.code}).") from exc

        if not response.text:
            raise LLMError("Gemini returned no content.")
        try:
            return response_model.model_validate_json(response.text)
        except ValidationError as exc:
            raise LLMError("Gemini returned data with an unexpected structure.") from exc
