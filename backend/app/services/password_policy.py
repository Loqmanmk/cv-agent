import unicodedata

MIN_LENGTH = 12
MAX_LENGTH = 128
MIN_DISTINCT_CHARACTERS = 5
MIN_NAME_LENGTH = 4
COMMON_PASSWORDS = frozenset(
    {
        "password1234",
        "password12345",
        "passwordpassword",
        "123456789012",
        "1234567890123",
        "qwertyuiop12",
        "qwertyuiopas",
        "iloveyou1234",
        "letmein123456",
        "welcome12345",
        "changeme1234",
        "administrator",
    }
)


def normalize_password(password: str) -> str:
    """The same text typed on different keyboards must give the same password."""
    return unicodedata.normalize("NFKC", password)


def password_problems(password: str, email: str) -> list[str]:
    """What is wrong with a new password. An empty list means it is acceptable."""
    problems: list[str] = []
    if len(password) < MIN_LENGTH:
        problems.append(f"Use at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        problems.append(f"Use at most {MAX_LENGTH} characters.")
    if len(set(password)) < MIN_DISTINCT_CHARACTERS:
        problems.append("Use more different characters.")
    name = email.split("@")[0].casefold()
    if len(name) >= MIN_NAME_LENGTH and name in password.casefold():
        problems.append("Do not use your email address in the password.")
    if password.casefold() in COMMON_PASSWORDS:
        problems.append("This password is too common.")
    return problems
