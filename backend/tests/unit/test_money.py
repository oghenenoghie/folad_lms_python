import pytest

from shared.money import CurrencyMismatchError, Money


def test_add_same_currency():
    total = Money(150_00, "NGN") + Money(50_00, "NGN")
    assert total == Money(200_00, "NGN")


def test_subtract_same_currency():
    remainder = Money(200_00, "NGN") - Money(50_00, "NGN")
    assert remainder == Money(150_00, "NGN")


def test_add_mismatched_currency_raises():
    with pytest.raises(CurrencyMismatchError):
        Money(100, "NGN") + Money(100, "USD")


def test_unsupported_currency_raises():
    with pytest.raises(ValueError):
        Money(100, "XXX")


def test_to_major_string():
    assert Money(123_456, "NGN").to_major_string() == "1234.56"
    assert Money(-50, "USD").to_major_string() == "-0.50"


def test_is_zero_and_negative():
    assert Money(0, "NGN").is_zero()
    assert Money(-1, "NGN").is_negative()
    assert not Money(1, "NGN").is_negative()


def test_immutable():
    m = Money(100, "NGN")
    with pytest.raises(Exception):
        m.amount_minor = 200
