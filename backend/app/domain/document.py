from abc import ABC, abstractmethod
from dataclasses import dataclass, field

MAX_CV_BYTES = 5_000_000


@dataclass(frozen=True)
class ExtractedImage:
    """An image found inside a document (the CV photo is one of them)."""

    data: bytes
    extension: str
    width: int
    height: int


@dataclass(frozen=True)
class ParsedDocument:
    """What we get out of an uploaded document."""

    text: str
    images: list[ExtractedImage] = field(default_factory=list)


class DocumentParser(ABC):
    """Contract for anything that can read an uploaded CV file."""

    @abstractmethod
    def parse(self, content: bytes) -> ParsedDocument:
        """Extract the text and the images from the raw file bytes."""


class InvalidPhotoError(Exception):
    """Raised when a photo cannot be used in a CV."""


class PhotoSanitizer(ABC):
    """Contract for anything that turns an untrusted image into a safe, small photo."""

    @abstractmethod
    def sanitize(self, data: bytes) -> ExtractedImage:
        """Return a clean photo, or raise InvalidPhotoError."""
