from pydantic import BaseModel

from app.domain.llm import LLMError, LLMProvider


class FakeLLMProvider(LLMProvider):
    """Returns a preset answer. Records the prompts it received."""

    def __init__(self, answer: BaseModel) -> None:
        self._answer = answer
        self.calls: list[tuple[str, str]] = []

    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        self.calls.append((system_prompt, user_prompt))
        if not isinstance(self._answer, response_model):
            raise LLMError(f"Fake answer is not a {response_model.__name__}")
        return self._answer
