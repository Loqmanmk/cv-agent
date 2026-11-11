from argon2 import PasswordHasher as RawArgon2

from app.domain.accounts import PasswordHasher
from app.infrastructure.argon2_hasher import Argon2PasswordHasher


def fast_hasher() -> Argon2PasswordHasher:
    """The cheapest Argon2 settings, so tests stay fast. Production uses the defaults."""
    return Argon2PasswordHasher(RawArgon2(time_cost=1, memory_cost=8, parallelism=1))


class CountingHasher(PasswordHasher):
    """Wraps a hasher and counts how often passwords are checked."""

    def __init__(self, inner: PasswordHasher) -> None:
        self._inner = inner
        self.verify_calls = 0

    def hash(self, password: str) -> str:
        return self._inner.hash(password)

    def verify(self, stored_hash: str, password: str) -> bool:
        self.verify_calls += 1
        return self._inner.verify(stored_hash, password)

    def needs_rehash(self, stored_hash: str) -> bool:
        return self._inner.needs_rehash(stored_hash)
