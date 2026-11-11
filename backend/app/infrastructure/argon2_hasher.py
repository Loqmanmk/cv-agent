from argon2 import PasswordHasher as Argon2
from argon2.exceptions import InvalidHashError, VerificationError

from app.domain.accounts import PasswordHasher


class Argon2PasswordHasher(PasswordHasher):
    """Argon2id with the library's current recommended settings, unless others are given."""

    def __init__(self, hasher: Argon2 | None = None) -> None:
        self._hasher = hasher or Argon2()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, stored_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(stored_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, stored_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(stored_hash)
        except InvalidHashError:
            return False
