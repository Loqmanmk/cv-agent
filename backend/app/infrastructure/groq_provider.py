import json
import logging

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

from app.domain.llm import LLMError, LLMProvider, LLMUnavailableError

logger = logging.getLogger(__name__)

API_URL = "https://api.groq.com/openai/v1/chat/completions"
TEMPERATURE = 0.2
TIMEOUT_SECONDS = 120.0
MAX_DETAIL_CHARS = 300
# How long to skip a model after a problem that is not a quota (seconds).
BAD_ANSWER_PAUSE = 1.0  # one bad answer: the next model tries at once, this one stays usable
TOO_LARGE_PAUSE = 60.0  # the request is bigger than the per-minute token budget of the model
GONE_PAUSE = 3600.0  # the model was retired: skip it for an hour
UNAVAILABLE_CODES = {429, 498, 500, 502, 503, 504}


def _retry_after(response: httpx.Response) -> float | None:
    """Groq's Retry-After header, in seconds."""
    value = response.headers.get("retry-after", "")
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None


class GroqProvider(LLMProvider):
    """AI provider backed by one Groq model, through its OpenAI-compatible API.

    The answer must follow the JSON schema of the expected model; it is validated here like
    every other provider's answer, so a wrong answer never reaches the application.
    """

    def __init__(self, api_key: SecretStr, model: str, http: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._http = http or httpx.Client(timeout=TIMEOUT_SECONDS)

    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        content = self._request(system_prompt, user_prompt, response_model)
        try:
            return response_model.model_validate_json(content)
        except ValidationError as exc:
            raise LLMUnavailableError(
                f"Groq {self._model} returned data with an unexpected structure.",
                BAD_ANSWER_PAUSE,
            ) from exc

    def _request(
        self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]
    ) -> str:
        body = {
            "model": self._model,
            "temperature": TEMPERATURE,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": response_model.model_json_schema(),
                    "strict": False,
                },
            },
        }
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
        try:
            response = self._http.post(API_URL, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Groq {self._model}: network error.") from exc
        if response.status_code != httpx.codes.OK:
            raise self._to_llm_error(response)
        content = self._content_of(response)
        logger.info("groq %s answered", self._model)
        return content

    def _content_of(self, response: httpx.Response) -> str:
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError(
                f"Groq {self._model} sent an unreadable answer.", BAD_ANSWER_PAUSE
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMUnavailableError(f"Groq {self._model} returned no content.", BAD_ANSWER_PAUSE)
        return content

    def _to_llm_error(self, response: httpx.Response) -> LLMError:
        code = response.status_code
        detail = self._detail(response)
        text = f"Groq {self._model} unavailable (code {code}): {detail}"
        if code in UNAVAILABLE_CODES:
            return LLMUnavailableError(text, _retry_after(response))
        if code == httpx.codes.REQUEST_ENTITY_TOO_LARGE:
            return LLMUnavailableError(text, TOO_LARGE_PAUSE)
        if code == httpx.codes.NOT_FOUND:
            return LLMUnavailableError(text, GONE_PAUSE)
        if code == httpx.codes.BAD_REQUEST and "json_validate_failed" in detail:
            return LLMUnavailableError(text, BAD_ANSWER_PAUSE)
        if code in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):
            return LLMError("Groq refused the API key. Check GROQ_API_KEY in backend/.env.")
        return LLMError(f"Groq request failed (code {code}).")

    @staticmethod
    def _detail(response: httpx.Response) -> str:
        """Groq's own error text, short. It never contains the API key."""
        try:
            error = response.json().get("error", {})
            message = f"{error.get('code', '')} {error.get('message', '')}".strip()
        except (ValueError, AttributeError):
            message = response.text
        return json.dumps(message)[1:-1][:MAX_DETAIL_CHARS]
