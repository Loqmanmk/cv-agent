import base64
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.domain.cv import CV
from app.domain.cv_labels import CVLabels
from app.domain.document import ExtractedImage

TEMPLATES = Path(__file__).parent / "templates"
MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class UnsupportedPhotoError(Exception):
    """Raised when the photo format cannot be embedded in the CV."""


def safe_url(value: str) -> str:
    """Return a clickable http(s) address, or an empty string if the value is not safe."""
    text = value.strip()
    if not text or any(character.isspace() for character in text):
        return ""
    candidate = text if "://" in text else f"https://{text}"
    parsed = urlparse(candidate)
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"} or "." not in host:
        return ""
    return candidate


class CVHtmlBuilder:
    """Fills the CV template. Every value is HTML-escaped."""

    def __init__(self) -> None:
        self._environment = Environment(
            loader=FileSystemLoader(TEMPLATES),
            autoescape=True,
            undefined=StrictUndefined,
        )
        self._environment.filters["safe_url"] = safe_url

    def build(
        self,
        cv: CV,
        photo: ExtractedImage | None,
        labels: CVLabels,
        font_size: float = 9.0,
        spacing: float = 1.0,
    ) -> str:
        template = self._environment.get_template("cv.html.j2")
        return template.render(
            cv=cv,
            labels=labels,
            photo_uri=self._photo_uri(photo),
            font_size=font_size,
            spacing=spacing,
        )

    @staticmethod
    def _photo_uri(photo: ExtractedImage | None) -> str | None:
        if photo is None:
            return None
        mime = MIME_TYPES.get(photo.extension.lower())
        if mime is None:
            raise UnsupportedPhotoError(f"Unsupported photo format: {photo.extension}")
        encoded = base64.b64encode(photo.data).decode("ascii")
        return f"data:{mime};base64,{encoded}"
