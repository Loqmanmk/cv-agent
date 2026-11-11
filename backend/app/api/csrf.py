from collections.abc import Sequence


def origin_allowed(origin: str | None, allowed_origins: Sequence[str]) -> bool:
    """Whether a state-changing request may come from this origin.

    Browsers always say where a request comes from. A missing header means the client is not a
    browser, which the CSRF token still covers. The special value "null" (sent from sandboxed
    pages and some redirects) is never in the allowed list, so it is refused.
    """
    if origin is None:
        return True
    return origin in allowed_origins
