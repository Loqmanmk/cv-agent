import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.llm import LLMError, LLMUnavailableError
from app.services.application_service import InvalidApplicationInputError
from app.services.cv_structurer import CVStructuringError
from app.services.job_analyzer import JobAnalysisError
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.letter_guard import LetterViolationError
from app.services.page_fitter import PageOverflowError
from app.services.tailoring_guard import TailoringViolationError

logger = logging.getLogger(__name__)

INPUT_ERRORS = (
    InvalidApplicationInputError,
    JobAnalysisError,
    CVStructuringError,
    UnsupportedLetterLanguageError,
    PageOverflowError,
)


def _unprocessable(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def _unavailable(_request: Request, exc: Exception) -> JSONResponse:
    logger.warning("AI unavailable: %s", exc)
    detail = "The AI service is busy or out of quota. Please try again later."
    return JSONResponse(status_code=503, content={"detail": detail})


def _bad_gateway(_request: Request, exc: Exception) -> JSONResponse:
    logger.warning("AI error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": "The AI service failed to answer."})


def _unfaithful(_request: Request, exc: Exception) -> JSONResponse:
    violations = list(getattr(exc, "violations", []))
    logger.warning("Guard rejected the AI result: %s", violations)
    detail = "The AI could not produce a faithful result. Please try again."
    return JSONResponse(status_code=502, content={"detail": detail, "violations": violations})


def register_error_handlers(app: FastAPI) -> None:
    for error_type in INPUT_ERRORS:
        app.add_exception_handler(error_type, _unprocessable)
    app.add_exception_handler(LLMUnavailableError, _unavailable)
    app.add_exception_handler(LLMError, _bad_gateway)
    app.add_exception_handler(TailoringViolationError, _unfaithful)
    app.add_exception_handler(LetterViolationError, _unfaithful)
