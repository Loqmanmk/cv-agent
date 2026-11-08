from dataclasses import dataclass

from app.domain.job_source import JobFetchError, JobTextExtractor, PageFetcher
from app.services.job_analyzer import MAX_CHARS

MIN_TEXT_CHARS = 200
NO_OFFER_FOUND = (
    "Could not find the job description on this page. It may need a login or JavaScript. "
    "Paste the text of the offer instead."
)


@dataclass(frozen=True)
class FetchedJobText:
    text: str
    truncated: bool
    source_url: str


class JobFetchService:
    """Downloads a job page and extracts the text of the offer from it."""

    def __init__(self, fetcher: PageFetcher, extractor: JobTextExtractor) -> None:
        self._fetcher = fetcher
        self._extractor = extractor

    def fetch_text(self, url: str) -> FetchedJobText:
        page = self._fetcher.fetch(url.strip())
        text = self._extractor.extract(page.html).strip()
        if len(text) < MIN_TEXT_CHARS:
            raise JobFetchError(NO_OFFER_FOUND)
        return FetchedJobText(text[:MAX_CHARS], len(text) > MAX_CHARS, page.final_url)
