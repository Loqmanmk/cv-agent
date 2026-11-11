from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.accounts import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidEmailError,
    WeakPasswordError,
)

ALREADY_REGISTERED = "An account with this email already exists."
INVALID_CREDENTIALS = "Invalid email or password."


def register_auth_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidEmailError)
    def invalid_email(_request: Request, exc: InvalidEmailError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(WeakPasswordError)
    def weak_password(_request: Request, exc: WeakPasswordError) -> JSONResponse:
        content = {"detail": "Choose a stronger password.", "problems": exc.problems}
        return JSONResponse(status_code=422, content=content)

    @app.exception_handler(EmailAlreadyRegisteredError)
    def already_registered(_request: Request, _exc: EmailAlreadyRegisteredError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": ALREADY_REGISTERED})

    @app.exception_handler(InvalidCredentialsError)
    def invalid_credentials(_request: Request, _exc: InvalidCredentialsError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": INVALID_CREDENTIALS})
