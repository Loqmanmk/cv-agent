import pytest
from pydantic import SecretStr

from app.api.google_dependencies import get_google_client
from app.api.google_flow import PendingSignIn
from app.infrastructure.google_oidc import GoogleOidcClient
from tests.test_config import IsolatedSettings

PENDING = PendingSignIn("state-1", "nonce-1", "verifier-1")


def test_the_values_come_back_unchanged_from_the_cookie() -> None:
    assert PendingSignIn.decode(PENDING.encode()) == PENDING


@pytest.mark.parametrize(
    "value",
    [None, "", "only.two", "a..c", "a.b.c.d", "x." * 300 + "x"],
    ids=["missing", "empty", "too-few", "empty-part", "too-many", "too-long"],
)
def test_a_missing_or_damaged_cookie_is_ignored(value: str | None) -> None:
    assert PendingSignIn.decode(value) is None


@pytest.mark.parametrize("state", [None, "", "state-2", "state-1 ", "état"])
def test_only_the_exact_state_matches(state: str | None) -> None:
    assert PENDING.state_matches(state) is False


def test_the_exact_state_matches() -> None:
    assert PENDING.state_matches("state-1") is True


def test_the_values_never_appear_in_a_printed_sign_in() -> None:
    printed = repr(PENDING)

    assert "state-1" not in printed
    assert "nonce-1" not in printed
    assert "verifier-1" not in printed


@pytest.mark.parametrize(
    ("client_id", "secret"),
    [("", SecretStr("secret")), ("id", None), ("id", SecretStr(""))],
    ids=["no-id", "no-secret", "empty-secret"],
)
def test_google_sign_in_is_off_until_it_is_configured(
    client_id: str, secret: SecretStr | None
) -> None:
    settings = IsolatedSettings(google_client_id=client_id, google_client_secret=secret)

    assert get_google_client(settings) is None


def test_a_configured_server_gets_one_shared_google_client() -> None:
    settings = IsolatedSettings(google_client_id="id", google_client_secret=SecretStr("secret"))

    client = get_google_client(settings)

    assert isinstance(client, GoogleOidcClient)
    assert get_google_client(settings) is client
