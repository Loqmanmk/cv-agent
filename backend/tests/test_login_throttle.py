from app.api.login_throttle import LoginThrottle
from app.api.rate_limit import RateLimiter


def make_throttle(per_address: int = 100, per_account: int = 100) -> LoginThrottle:
    return LoginThrottle(RateLimiter(per_address, 60), RateLimiter(per_account, 60))


def test_attempts_within_the_limits_are_allowed() -> None:
    throttle = make_throttle(per_address=2, per_account=2)

    assert throttle.acquire("1.1.1.1", "jane@example.com") == 0.0
    assert throttle.acquire("1.1.1.1", "jane@example.com") == 0.0


def test_one_address_is_blocked_whatever_the_accounts_it_tries() -> None:
    throttle = make_throttle(per_address=2)
    throttle.acquire("1.1.1.1", "a@example.com")
    throttle.acquire("1.1.1.1", "b@example.com")

    assert throttle.acquire("1.1.1.1", "c@example.com") > 0
    assert throttle.acquire("2.2.2.2", "c@example.com") == 0.0


def test_one_account_is_blocked_whatever_the_addresses_it_is_attacked_from() -> None:
    throttle = make_throttle(per_account=2)
    throttle.acquire("1.1.1.1", "jane@example.com")
    throttle.acquire("2.2.2.2", "jane@example.com")

    assert throttle.acquire("3.3.3.3", "jane@example.com") > 0
    assert throttle.acquire("3.3.3.3", "other@example.com") == 0.0


def test_the_account_is_the_same_whatever_the_case_or_the_spaces_of_the_email() -> None:
    throttle = make_throttle(per_account=2)
    throttle.acquire("1.1.1.1", "Jane@Example.com")
    throttle.acquire("1.1.1.2", " jane@example.com ")

    assert throttle.acquire("1.1.1.3", "JANE@example.com") > 0


def test_an_address_that_is_blocked_does_not_use_up_the_account_budget() -> None:
    address = RateLimiter(1, 60)
    account = RateLimiter(2, 60)
    throttle = LoginThrottle(address, account)
    throttle.acquire("1.1.1.1", "jane@example.com")

    throttle.acquire("1.1.1.1", "jane@example.com")
    throttle.acquire("1.1.1.1", "jane@example.com")

    assert account.tracked_keys == 1
    assert throttle.acquire("9.9.9.9", "jane@example.com") == 0.0
