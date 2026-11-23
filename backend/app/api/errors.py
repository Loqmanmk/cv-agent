import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.domain.document import InvalidPhotoError
from app.domain.job_source import JobFetchError
from app.domain.jobs import JobFailure, JobLimitError
from app.domain.llm import LLMError, LLMUnavailableError
from app.domain.tracker import ApplicationNotFoundError, InvalidTrackerInputError
from app.services.application_service import InvalidApplicationInputError
from app.services.cv_structurer import CVStructuringError
from app.services.job_analyzer import JobAnalysisError
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.letter_guard import LetterViolationError
from app.services.page_fitter import PageOverflowError
from app.services.tailoring_guard import TailoringViolationError
from app.services.translation_guard import TranslationViolationError

logger = logging.getLogger(__name__)

INPUT_ERRORS = (
    InvalidApplicationInputError,
    InvalidPhotoError,
    InvalidTrackerInputError,
    JobAnalysisError,
    JobFetchError,
    CVStructuringError,
    UnsupportedLetterLanguageError,
    PageOverflowError,
)


UNFAITHFUL_ERRORS = (TailoringViolationError, LetterViolationError, TranslationViolationError)
BUSY = "The AI service is busy or out of quota. Please try again later."
UNEXPECTED = "Something went wrong. Please try again."


def describe_error(exc: Exception) -> JobFailure:
    """The status and message the user gets for an error, for a direct answer or a job.

    Details of the AI providers and of unexpected errors stay in the logs: they can hold
    quota information or internals the user does not need.
    """
    if isinstance(exc, UNFAITHFUL_ERRORS):
        violations = [str(item) for item in getattr(exc, "violations", [])]
        logger.warning("Guard rejected the AI result: %s", violations)
        detail = "The AI could not produce a faithful result. Please try again."
        return JobFailure(502, detail, violations)
    if isinstance(exc, LLMUnavailableError):
        logger.warning("AI unavailable: %s", exc)
        return JobFailure(503, BUSY)
    if isinstance(exc, LLMError):
        logger.warning("AI error: %s", exc)
        return JobFailure(502, "The AI service failed to answer.")
    if isinstance(exc, INPUT_ERRORS):
        return JobFailure(422, str(exc))
    if isinstance(exc, JobLimitError):
        detail = "An application is already being created. Wait for it to finish."
        return JobFailure(409, detail)
    if isinstance(exc, ApplicationNotFoundError):
        return JobFailure(404, "Application not found.")
    if isinstance(exc, OperationalError):
        logger.error("Database unavailable: %s", type(exc).__name__)
        return JobFailure(503, "The database is unavailable. Please try again later.")
    logger.error("Unexpected error", exc_info=exc)
    return JobFailure(500, UNEXPECTED)


def _answer(_request: Request, exc: Exception) -> JSONResponse:
    failure = describe_error(exc)
    content: dict[str, object] = {"detail": failure.detail}
    if isinstance(exc, UNFAITHFUL_ERRORS):
        content["violations"] = failure.violations
    return JSONResponse(status_code=failure.status, content=content)


def register_error_handlers(app: FastAPI) -> None:
    handled = (
        *INPUT_ERRORS,
        ApplicationNotFoundError,
        JobLimitError,
        OperationalError,
        LLMUnavailableError,
        LLMError,
        *UNFAITHFUL_ERRORS,
    )
    for error_type in handled:
        app.add_exception_handler(error_type, _answer)
