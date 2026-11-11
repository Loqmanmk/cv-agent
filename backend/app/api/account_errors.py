from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.plans import QuotaExceededError, UnknownUserError
from app.domain.profile import InvalidProfileError, ProfileIncompleteError


def register_account_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidProfileError)
    def invalid_profile(_request: Request, exc: InvalidProfileError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ProfileIncompleteError)
    def incomplete_profile(_request: Request, exc: ProfileIncompleteError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(QuotaExceededError)
    def quota_exceeded(_request: Request, exc: QuotaExceededError) -> JSONResponse:
        content = {
            "detail": str(exc),
            "limit": exc.limit,
            "resets_at": exc.resets_at.isoformat(),
        }
        return JSONResponse(status_code=402, content=content)

    @app.exception_handler(UnknownUserError)
    def unknown_user(_request: Request, _exc: UnknownUserError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": "Please log in."})
