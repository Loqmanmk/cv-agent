import pytest

from app.domain.job_source import FetchedPage, JobFetchError, JobTextExtractor, PageFetcher
from app.services.job_analyzer import MAX_CHARS
from app.services.job_fetch_service import MIN_TEXT_CHARS, NO_OFFER_FOUND, JobFetchService

OFFER = "Python developer wanted. " * 20


class FakeFetcher(PageFetcher):
    def __init__(self, final_url: str = "https://example.com/final") -> None:
        self.urls: list[str] = []
        self._final_url = final_url

    def fetch(self, url: str) -> FetchedPage:
        self.urls.append(url)
        return FetchedPage("<html>page</html>", self._final_url)


class FailingFetcher(PageFetcher):
    def fetch(self, url: str) -> FetchedPage:
        raise JobFetchError("The page was not found. Check the link.")


class FakeExtractor(JobTextExtractor):
    def __init__(self, text: str) -> None:
        self._text = text

    def extract(self, html: str) -> str:
        return self._text


def test_returns_the_extracted_text_and_the_final_address() -> None:
    result = JobFetchService(FakeFetcher(), FakeExtractor(f"  {OFFER}  ")).fetch_text("https://x.y")

    assert result.text == OFFER.strip()
    assert result.truncated is False
    assert result.source_url == "https://example.com/final"


def test_the_link_is_trimmed_before_fetching() -> None:
    fetcher = FakeFetcher()

    JobFetchService(fetcher, FakeExtractor(OFFER)).fetch_text("  https://example.com/job  ")

    assert fetcher.urls == ["https://example.com/job"]


def test_text_that_is_too_long_is_shortened_and_flagged() -> None:
    service = JobFetchService(FakeFetcher(), FakeExtractor("x" * (MAX_CHARS + 500)))

    result = service.fetch_text("https://x.y")

    assert len(result.text) == MAX_CHARS
    assert result.truncated is True


def test_text_of_exactly_the_maximum_is_not_flagged() -> None:
    service = JobFetchService(FakeFetcher(), FakeExtractor("x" * MAX_CHARS))

    assert service.fetch_text("https://x.y").truncated is False


@pytest.mark.parametrize("text", ["", "   ", "x" * (MIN_TEXT_CHARS - 1)])
def test_a_page_without_enough_text_is_refused(text: str) -> None:
    with pytest.raises(JobFetchError) as raised:
        JobFetchService(FakeFetcher(), FakeExtractor(text)).fetch_text("https://x.y")

    assert str(raised.value) == NO_OFFER_FOUND


def test_download_errors_are_passed_on() -> None:
    with pytest.raises(JobFetchError, match="not found"):
        JobFetchService(FailingFetcher(), FakeExtractor(OFFER)).fetch_text("https://x.y")
