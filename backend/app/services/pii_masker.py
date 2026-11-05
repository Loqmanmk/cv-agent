import re
from collections.abc import Callable
from dataclasses import dataclass

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"(?:https?://|www\.)\S+|(?:linkedin\.com|github\.com)/\S+")
PHONE = re.compile(r"\+?\d[\d \t().-]{7,}\d")
MIN_PHONE_DIGITS = 9
MAX_PHONE_DIGITS = 15
TRAILING_PUNCTUATION = ".,;:)\"'"


@dataclass(frozen=True)
class MaskedText:
    text: str
    mapping: dict[str, str]


def _looks_like_phone(value: str) -> bool:
    digits = sum(character.isdigit() for character in value)
    return MIN_PHONE_DIGITS <= digits <= MAX_PHONE_DIGITS


class PiiMasker:
    """Replaces emails, links and phone numbers with placeholders."""

    def mask(self, text: str) -> MaskedText:
        mapping: dict[str, str] = {}
        masked = self._replace(text, EMAIL, "EMAIL", mapping)
        masked = self._replace(masked, URL, "URL", mapping)
        masked = self._replace(masked, PHONE, "PHONE", mapping, _looks_like_phone)
        return MaskedText(masked, mapping)

    @staticmethod
    def restore(text: str, mapping: dict[str, str]) -> str:
        for placeholder, value in mapping.items():
            text = text.replace(placeholder, value)
        return text

    @staticmethod
    def _replace(
        text: str,
        pattern: re.Pattern[str],
        label: str,
        mapping: dict[str, str],
        accept: Callable[[str], bool] | None = None,
    ) -> str:
        def substitute(match: re.Match[str]) -> str:
            value = match.group(0)
            if accept is not None and not accept(value):
                return value
            core = value.rstrip(TRAILING_PUNCTUATION)
            tail = value[len(core) :]
            known = next((key for key, stored in mapping.items() if stored == core), None)
            if known is None:
                count = sum(key.startswith(f"[[{label}_") for key in mapping)
                known = f"[[{label}_{count + 1}]]"
                mapping[known] = core
            return known + tail

        return pattern.sub(substitute, text)
