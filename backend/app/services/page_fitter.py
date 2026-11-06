from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.domain.pdf import PdfPageCounter


@dataclass(frozen=True)
class FitSettings:
    """Font size (in pt) and spacing factor used to render a document."""

    font_size: float
    spacing: float


@dataclass(frozen=True)
class FitResult:
    pdf: bytes
    settings: FitSettings


# CVs: from the most comfortable layout to the most compact. Never below 8 pt.
LADDER: tuple[FitSettings, ...] = (
    FitSettings(9.0, 1.0),
    FitSettings(9.0, 0.8),
    FitSettings(8.75, 0.8),
    FitSettings(8.5, 0.7),
    FitSettings(8.25, 0.6),
    FitSettings(8.0, 0.5),
)

# Cover letters: larger text than a CV. Never below 9.5 pt.
LETTER_LADDER: tuple[FitSettings, ...] = (
    FitSettings(11.0, 1.0),
    FitSettings(10.5, 0.9),
    FitSettings(10.0, 0.8),
    FitSettings(9.5, 0.7),
)


class PageOverflowError(Exception):
    """Raised when the content does not fit on one page, even with the most compact layout."""


class OnePageFitter:
    """Finds the most comfortable layout that gives exactly one page."""

    def __init__(self, counter: PdfPageCounter, ladder: Sequence[FitSettings] = LADDER) -> None:
        if not ladder:
            raise ValueError("The ladder needs at least one setting.")
        self._counter = counter
        self._ladder = list(ladder)

    def fit(self, render: Callable[[FitSettings], bytes]) -> FitResult:
        for settings in self._ladder:
            pdf = render(settings)
            if self._counter.count(pdf) == 1:
                return FitResult(pdf, settings)
        raise PageOverflowError(
            "The content does not fit on one page, even with the most compact layout. "
            "Shorten the text or remove some content."
        )
