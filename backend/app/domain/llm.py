from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMError(Exception):
    """Raised when an AI provider fails or returns unusable output."""


class LLMUnavailableError(LLMError):
    """Raised when a provider is out of quota, overloaded or unreachable."""


class LLMProvider(ABC):
    """Contract for any AI provider able to return structured data."""

    @abstractmethod
    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        """Return an instance of `response_model` built from the prompts."""
