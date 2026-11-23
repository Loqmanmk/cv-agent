import threading
from collections.abc import Callable
from concurrent.futures import Executor, Future
from typing import Any

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


class SequenceLLMProvider(LLMProvider):
    """Returns preset answers in order. Records the prompts it received.

    Each call takes the first preset answer of the type it asks for, so calls made at the
    same time from two threads still get the right answers.
    """

    def __init__(self, answers: list[BaseModel]) -> None:
        self._answers = list(answers)
        self._lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []

    def generate[T: BaseModel](
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        with self._lock:
            self.calls.append((system_prompt, user_prompt))
            for index, answer in enumerate(self._answers):
                if isinstance(answer, response_model):
                    return self._answers.pop(index)  # type: ignore[return-value]
            raise LLMError(f"No preset answer left for {response_model.__name__}")


class ImmediateExecutor(Executor):
    """Runs each task at once in the calling thread, so a background job is done on return."""

    def submit[R](self, fn: Callable[..., R], /, *args: Any, **kwargs: Any) -> Future[R]:
        future: Future[R] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:  # noqa: BLE001 - kept in the future, like a real executor
            future.set_exception(exc)
        return future
