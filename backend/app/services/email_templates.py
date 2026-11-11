from app.domain.mail import EmailMessage

PRODUCT = "CV Agent"


def verification_email(to: str, link: str) -> EmailMessage:
    text = (
        f"Hello,\n\nConfirm your email address for {PRODUCT} by opening this link:\n\n"
        f"{link}\n\n"
        "The link works once and expires in 48 hours.\n\n"
        "If you did not create an account, ignore this email: nothing will happen.\n"
    )
    return EmailMessage(to=to, subject=f"Confirm your email address for {PRODUCT}", text=text)


def account_exists_email(to: str, login_link: str) -> EmailMessage:
    text = (
        f"Hello,\n\nSomeone tried to create a {PRODUCT} account with this email address, "
        "but you already have one.\n\n"
        f"If it was you, log in here:\n\n{login_link}\n\n"
        "If it was not you, ignore this email: your account is safe.\n"
    )
    return EmailMessage(to=to, subject=f"You already have a {PRODUCT} account", text=text)
