from pydantic import BaseModel

from app.domain.llm import LLMProvider
from app.services.pii_masker import PiiMasker


class MaskingLLMProvider(LLMProvider):
    """Hides personal contact details from the wrapped provider."""

    def __init__(self, inner: LLMProvider, masker: PiiMasker | None = None) -> None:
        self._inner = inner
        self._masker = masker or PiiMasker()

    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        masked = self._masker.mask(user_prompt)
        result = self._inner.generate(system_prompt, masked.text, response_model)
        restored = self._restore_value(result.model_dump(), masked.mapping)
        return response_model.model_validate(restored)

    def _restore_value(self, value: object, mapping: dict[str, str]) -> object:
        if isinstance(value, str):
            return self._masker.restore(value, mapping)
        if isinstance(value, list):
            return [self._restore_value(item, mapping) for item in value]
        if isinstance(value, dict):
            return {key: self._restore_value(item, mapping) for key, item in value.items()}
        return value
