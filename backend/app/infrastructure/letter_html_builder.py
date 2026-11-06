from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.domain.letter import CoverLetter
from app.infrastructure.cv_html_builder import TEMPLATES


class LetterHtmlBuilder:
    """Fills the cover letter template. Every value is HTML-escaped."""

    def __init__(self) -> None:
        self._environment = Environment(
            loader=FileSystemLoader(TEMPLATES),
            autoescape=True,
            undefined=StrictUndefined,
        )

    def build(
        self,
        letter: CoverLetter,
        font_size: float = 11.0,
        spacing: float = 1.0,
        lang: str = "fr",
        direction: str = "ltr",
    ) -> str:
        template = self._environment.get_template("letter.html.j2")
        return template.render(
            letter=letter,
            font_size=font_size,
            spacing=spacing,
            lang=lang,
            direction=direction,
        )
