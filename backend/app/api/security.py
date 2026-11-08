from collections.abc import Awaitable, Callable

from fastapi import Request, Response

# The API only returns JSON and PDF files, never a web page, so everything can be locked down.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
HSTS_VALUE = "max-age=31536000; includeSubDomains"

CallNext = Callable[[Request], Awaitable[Response]]


def security_headers_middleware(hsts: bool) -> Callable[[Request, CallNext], Awaitable[Response]]:
    """Add the security headers to every answer. HSTS only makes sense over HTTPS."""

    async def add_headers(request: Request, call_next: CallNext) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        if hsts:
            response.headers["Strict-Transport-Security"] = HSTS_VALUE
        return response

    return add_headers
