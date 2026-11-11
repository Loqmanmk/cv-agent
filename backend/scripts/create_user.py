import getpass
import sys

from app.core.config import get_settings
from app.domain.accounts import (
    EmailAlreadyRegisteredError,
    InvalidEmailError,
    WeakPasswordError,
)
from app.infrastructure.argon2_hasher import Argon2PasswordHasher
from app.infrastructure.db.engine import create_db_engine
from app.infrastructure.db.postgres_users import PostgresUserRepository
from app.services.account_service import AccountService


def main(email: str) -> None:
    url = get_settings().database_url
    if url is None:
        sys.exit("DATABASE_URL is missing in backend/.env")
    password = getpass.getpass("Password (not shown): ")
    if password != getpass.getpass("Repeat the password: "):
        sys.exit("The passwords differ.")
    service = AccountService(
        PostgresUserRepository(create_db_engine(url.get_secret_value())),
        Argon2PasswordHasher(),
    )
    try:
        account = service.register(email, password)
    except InvalidEmailError as error:
        sys.exit(str(error))
    except WeakPasswordError as error:
        sys.exit("Weak password: " + " ".join(error.problems))
    except EmailAlreadyRegisteredError:
        sys.exit("An account with this email already exists.")
    print(f"Account created for {account.email}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python -m scripts.create_user EMAIL")
    main(sys.argv[1])
