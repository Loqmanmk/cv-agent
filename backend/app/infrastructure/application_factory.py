from app.core.config import Settings
from app.infrastructure.cv_html_builder import CVHtmlBuilder
from app.infrastructure.docx_parser import DocxParser
from app.infrastructure.letter_html_builder import LetterHtmlBuilder
from app.infrastructure.llm_factory import build_gemini_chain
from app.infrastructure.pdf_converter import PlaywrightPdfConverter
from app.infrastructure.pdf_page_counter import PyMuPdfPageCounter
from app.infrastructure.pdf_parser import PdfParser
from app.infrastructure.photo_sanitizer import PillowPhotoSanitizer
from app.infrastructure.safe_page_fetcher import SafePageFetcher
from app.infrastructure.trafilatura_extractor import TrafilaturaExtractor
from app.services.application_service import ApplicationService
from app.services.document_renderer import DocumentRenderer
from app.services.job_fetch_service import JobFetchService
from app.services.render_service import RenderService


def build_application_service(settings: Settings) -> ApplicationService:
    """Wire the real implementations together."""
    return ApplicationService(
        llm=build_gemini_chain(settings),
        converter=PlaywrightPdfConverter(),
        counter=PyMuPdfPageCounter(),
        cv_html=CVHtmlBuilder(),
        letter_html=LetterHtmlBuilder(),
        parsers={".docx": DocxParser(), ".pdf": PdfParser()},
        photo_sanitizer=PillowPhotoSanitizer(),
    )


def build_render_service() -> RenderService:
    """The render service needs no AI, so it needs no settings."""
    renderer = DocumentRenderer(
        PlaywrightPdfConverter(),
        PyMuPdfPageCounter(),
        CVHtmlBuilder(),
        LetterHtmlBuilder(),
    )
    return RenderService(renderer, PillowPhotoSanitizer())


def build_job_fetch_service() -> JobFetchService:
    """Fetching a public page needs no AI and no settings."""
    return JobFetchService(SafePageFetcher(), TrafilaturaExtractor())
