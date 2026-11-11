from email_validator import EmailNotValidError, validate_email

from app.domain.accounts import InvalidEmailError

MESSAGE = "Enter a valid email address."
RESERVED_SUFFIXES = (".invalid",)


def normalize_email(raw: str) -> str:
    """A checked, lowercase address. It is the key of the account, so it must be stable."""
    try:
        address = validate_email(raw.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise InvalidEmailError(MESSAGE) from exc
    if address.endswith(RESERVED_SUFFIXES):
        raise InvalidEmailError(MESSAGE)
    return address
