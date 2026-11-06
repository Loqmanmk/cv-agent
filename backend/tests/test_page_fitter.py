from collections.abc import Callable

import pytest

from app.domain.pdf import PdfPageCounter
from app.services.page_fitter import LADDER, FitSettings, OnePageFitter, PageOverflowError

SMALL = [FitSettings(9.0, 1.0), FitSettings(8.5, 0.8), FitSettings(8.0, 0.5)]


class FakeCounter(PdfPageCounter):
    """Counts pages from a table: pdf bytes to number of pages."""

    def __init__(self, pages: dict[bytes, int]) -> None:
        self._pages = pages

    def count(self, pdf: bytes) -> int:
        return self._pages[pdf]


def key(settings: FitSettings) -> bytes:
    return f"{settings.font_size}/{settings.spacing}".encode()


def fitter_with(pages: list[int]) -> OnePageFitter:
    table = {key(setting): count for setting, count in zip(SMALL, pages, strict=True)}
    return OnePageFitter(FakeCounter(table), SMALL)


def recorder() -> tuple[list[FitSettings], Callable[[FitSettings], bytes]]:
    seen: list[FitSettings] = []

    def render(settings: FitSettings) -> bytes:
        seen.append(settings)
        return key(settings)

    return seen, render


def test_keeps_the_most_comfortable_layout_when_it_fits() -> None:
    seen, render = recorder()

    result = fitter_with([1, 1, 1]).fit(render)

    assert result.settings == SMALL[0]
    assert seen == [SMALL[0]]


def test_moves_to_a_more_compact_layout_when_the_page_overflows() -> None:
    seen, render = recorder()

    result = fitter_with([2, 1, 1]).fit(render)

    assert result.settings == SMALL[1]
    assert result.pdf == key(SMALL[1])
    assert seen == SMALL[:2]


def test_raises_when_nothing_fits() -> None:
    seen, render = recorder()

    with pytest.raises(PageOverflowError):
        fitter_with([2, 2, 3]).fit(render)

    assert seen == SMALL


def test_requires_a_non_empty_ladder() -> None:
    with pytest.raises(ValueError, match="at least one"):
        OnePageFitter(FakeCounter({}), [])


def test_default_ladder_never_goes_below_the_readability_floor() -> None:
    sizes = [setting.font_size for setting in LADDER]

    assert min(sizes) >= 8.0
    assert sizes == sorted(sizes, reverse=True)
