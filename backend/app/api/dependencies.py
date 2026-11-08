import math
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.api.rate_limit import RateLimiter
from app.core.config import get_settings
from app.infrastructure.application_factory import (
    build_application_service,
    build_job_fetch_service,
    build_render_service,
)
from app.services.application_service import ApplicationService
from app.services.job_fetch_service import JobFetchService
from app.services.render_service import RenderService

WINDOW_SECONDS = 3600


@lru_cache
def get_application_service() -> ApplicationService:
    return build_application_service(get_settings())


@lru_cache
def get_render_service() -> RenderService:
    return build_render_service()


@lru_cache
def get_job_fetch_service() -> JobFetchService:
    return build_job_fetch_service()


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings().rate_limit_per_hour, WINDOW_SECONDS)


@lru_cache
def get_render_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings().render_rate_limit_per_hour, WINDOW_SECONDS)


@lru_cache
def get_fetch_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings().fetch_rate_limit_per_hour, WINDOW_SECONDS)


def _enforce(request: Request, limiter: RateLimiter) -> None:
    client = request.client.host if request.client else "unknown"
    wait = limiter.acquire(client)
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(math.ceil(wait))},
        )


def enforce_rate_limit(
    request: Request,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    _enforce(request, limiter)


def enforce_render_rate_limit(
    request: Request,
    limiter: Annotated[RateLimiter, Depends(get_render_rate_limiter)],
) -> None:
    _enforce(request, limiter)


def enforce_fetch_rate_limit(
    request: Request,
    limiter: Annotated[RateLimiter, Depends(get_fetch_rate_limiter)],
) -> None:
    _enforce(request, limiter)
