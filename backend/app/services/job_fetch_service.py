import re
from dataclasses import dataclass

from app.domain.job_source import JobFetchError, JobTextExtractor, PageFetcher
from app.services.job_analyzer import MAX_CHARS

MIN_TEXT_CHARS = 200
NO_OFFER_FOUND = (
    "Could not find the job description on this page. It may need a login or JavaScript. "
    "Paste the text of the offer instead."
)
HORIZONTAL_SPACE = re.compile(r"[^\S\n]+")
BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class FetchedJobText:
    text: str
    truncated: bool
    source_url: str


def tidy(text: str) -> str:
    """Remove the indentation and the empty lines that web pages leave in extracted text."""
    lines = (HORIZONTAL_SPACE.sub(" ", line).strip() for line in text.splitlines())
    return BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


class JobFetchService:
    """Downloads a job page and extracts the text of the offer from it."""

    def __init__(self, fetcher: PageFetcher, extractor: JobTextExtractor) -> None:
        self._fetcher = fetcher
        self._extractor = extractor

    def fetch_text(self, url: str) -> FetchedJobText:
        page = self._fetcher.fetch(url.strip())
        text = tidy(self._extractor.extract(page.html))
        if len(text) < MIN_TEXT_CHARS:
            raise JobFetchError(NO_OFFER_FOUND)
        return FetchedJobText(text[:MAX_CHARS], len(text) > MAX_CHARS, page.final_url)
