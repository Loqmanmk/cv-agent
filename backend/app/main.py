import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.errors import register_error_handlers
from app.api.routes import router
from app.api.tracker_routes import router as tracker_router
from app.core.config import Settings, get_settings
from app.services.application_service import MAX_CV_BYTES

MAX_REQUEST_BYTES = MAX_CV_BYTES + 200_000

logging.basicConfig(level=logging.INFO)


async def reject_oversized_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_REQUEST_BYTES:
        return JSONResponse(status_code=413, content={"detail": "The upload is too large."})
    return await call_next(request)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="CV Agent")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.middleware("http")(reject_oversized_requests)
    register_error_handlers(app)
    app.include_router(router)
    app.include_router(tracker_router)
    return app


app = create_app()
