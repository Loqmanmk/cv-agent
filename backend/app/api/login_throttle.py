import hashlib

from app.api.rate_limit import RateLimiter


def _account_key(email: str) -> str:
    """A fixed-size key, so long or hostile emails cannot grow the memory."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


class LoginThrottle:
    """Limits login attempts per address and per account, before any password is hashed."""

    def __init__(self, per_address: RateLimiter, per_account: RateLimiter) -> None:
        self._per_address = per_address
        self._per_account = per_account

    def acquire(self, address: str, email: str) -> float:
        """0.0 when the attempt may go on, otherwise the seconds to wait."""
        wait = self._per_address.acquire(address)
        if wait > 0:
            return wait
        return self._per_account.acquire(_account_key(email))
