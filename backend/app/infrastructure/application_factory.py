from app.core.config import Settings
from app.infrastructure.cv_html_builder import CVHtmlBuilder
from app.infrastructure.docx_parser import DocxParser
from app.infrastructure.letter_html_builder import LetterHtmlBuilder
from app.infrastructure.llm_factory import build_gemini_chain
from app.infrastructure.pdf_converter import PlaywrightPdfConverter
from app.infrastructure.pdf_page_counter import PyMuPdfPageCounter
from app.infrastructure.pdf_parser import PdfParser
from app.services.application_service import ApplicationService


def build_application_service(settings: Settings) -> ApplicationService:
    """Wire the real implementations together."""
    return ApplicationService(
        llm=build_gemini_chain(settings),
        converter=PlaywrightPdfConverter(),
        counter=PyMuPdfPageCounter(),
        cv_html=CVHtmlBuilder(),
        letter_html=LetterHtmlBuilder(),
        parsers={".docx": DocxParser(), ".pdf": PdfParser()},
    )
