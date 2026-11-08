from abc import ABC, abstractmethod
from dataclasses import dataclass


class JobFetchError(Exception):
    """Raised when a job page cannot be fetched. The message is safe to show to the user."""


@dataclass(frozen=True)
class FetchedPage:
    html: str
    final_url: str


class PageFetcher(ABC):
    """Contract for anything that can download a web page."""

    @abstractmethod
    def fetch(self, url: str) -> FetchedPage:
        """Return the page, or raise JobFetchError."""


class JobTextExtractor(ABC):
    """Contract for anything that can pull the readable text out of an HTML page."""

    @abstractmethod
    def extract(self, html: str) -> str:
        """Return the main text of the page, or an empty string."""
