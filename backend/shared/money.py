"""Money value object: integer minor units, per §A3 of ARCHITECTURE.md.

All monetary amounts are stored and computed as integer minor units
(e.g. kobo, cents) to avoid float/Decimal rounding and serialization
edge cases at API boundaries. `Money` never exposes or accepts a float.
"""
from __future__ import annotations

from dataclasses import dataclass

# Minor-unit exponent per ISO 4217 currency code (extend as needed).
_CURRENCY_EXPONENTS: dict[str, int] = {
    "NGN": 2,
    "USD": 2,
    "GBP": 2,
    "EUR": 2,
    "KES": 2,
    "GHS": 2,
    "ZAR": 2,
}


class CurrencyMismatchError(ValueError):
    """Raised when an operation mixes two different currency codes."""


@dataclass(frozen=True, slots=True)
class Money:
    """An immutable amount in integer minor units of a given currency."""

    amount_minor: int
    currency_code: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool):
            raise TypeError("amount_minor must be an int (minor units)")
        code = self.currency_code.upper()
        if code not in _CURRENCY_EXPONENTS:
            raise ValueError(f"Unsupported currency code: {self.currency_code!r}")
        object.__setattr__(self, "currency_code", code)

    @property
    def exponent(self) -> int:
        return _CURRENCY_EXPONENTS[self.currency_code]

    def _check_same_currency(self, other: "Money") -> None:
        if self.currency_code != other.currency_code:
            raise CurrencyMismatchError(
                f"Cannot combine {self.currency_code} with {other.currency_code}"
            )

    def add(self, other: "Money") -> "Money":
        self._check_same_currency(other)
        return Money(self.amount_minor + other.amount_minor, self.currency_code)

    def subtract(self, other: "Money") -> "Money":
        self._check_same_currency(other)
        return Money(self.amount_minor - other.amount_minor, self.currency_code)

    def is_negative(self) -> bool:
        return self.amount_minor < 0

    def is_zero(self) -> bool:
        return self.amount_minor == 0

    def to_major_string(self) -> str:
        """Render as a major-unit decimal string for display only, e.g. '1234.56'."""
        exp = self.exponent
        divisor = 10**exp
        major, minor = divmod(abs(self.amount_minor), divisor)
        sign = "-" if self.amount_minor < 0 else ""
        return f"{sign}{major}.{minor:0{exp}d}" if exp else f"{sign}{major}"

    def __add__(self, other: "Money") -> "Money":
        return self.add(other)

    def __sub__(self, other: "Money") -> "Money":
        return self.subtract(other)

    def __str__(self) -> str:
        return f"{self.to_major_string()} {self.currency_code}"
