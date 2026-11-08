import pytest

from app.infrastructure.safe_page_fetcher import is_default_port, is_public_address

PUBLIC = [
    "1.1.1.1",
    "8.8.8.8",
    "93.184.216.34",
    "2606:4700:4700::1111",
    "2001:4860:4860::8888",
    "::ffff:8.8.8.8",
]
NOT_PUBLIC = [
    "127.0.0.1",
    "0.0.0.0",  # noqa: S104 - must be refused, so it belongs in this list
    "10.0.0.5",
    "172.16.0.1",
    "192.168.1.1",
    "169.254.169.254",
    "100.64.0.1",
    "192.0.2.1",
    "198.18.0.1",
    "224.0.0.1",
    "239.255.255.250",
    "255.255.255.255",
    "::1",
    "::",
    "fe80::1",
    "fc00::1",
    "ff02::1",
    "::ffff:127.0.0.1",
    "::ffff:10.0.0.1",
    "2002:7f00:1::",
    "64:ff9b::7f00:1",
    "2001:0:4136:e378::",
    "",
    "not an address",
]


@pytest.mark.parametrize("address", PUBLIC)
def test_public_addresses_are_allowed(address: str) -> None:
    assert is_public_address(address) is True


@pytest.mark.parametrize("address", NOT_PUBLIC)
def test_internal_and_special_addresses_are_refused(address: str) -> None:
    assert is_public_address(address) is False


def test_only_the_default_port_of_each_scheme_is_allowed() -> None:
    assert is_default_port("http", 80)
    assert is_default_port("https", 443)
    assert not is_default_port("http", 443)
    assert not is_default_port("https", 6379)
    assert not is_default_port("http", 0)
