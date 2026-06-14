"""Money — integer-cents, currency-tagged, total-ordering.

Float money is a bug. All amounts are integer cents in a tagged currency.
Arithmetic across different currencies raises rather than silently coercing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

# ISO 4217 — keep this minimal until we need more.
_VALID_CURRENCIES: frozenset[str] = frozenset(
    {"USD", "EUR", "GBP", "INR", "JPY", "CAD", "AUD", "BRL", "MXN", "SGD"}
)


class CurrencyMismatchError(ValueError):
    """Raised when two Money values with different currencies are combined."""


@dataclass(frozen=True, slots=True, order=False)
class Money:
    """Integer-cents amount with currency tag.

    Equality and ordering compare amounts only when currencies match;
    cross-currency ordering raises.
    """

    amount_cents: int
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount_cents, int):
            raise TypeError("Money.amount_cents must be an int (cents)")
        if self.currency not in _VALID_CURRENCIES:
            raise ValueError(f"Unsupported currency: {self.currency!r}")

    # ---- Constructors -------------------------------------------------------
    @classmethod
    def zero(cls, currency: str) -> Self:
        return cls(0, currency)

    @classmethod
    def from_major_units(cls, major: int | float, currency: str) -> Self:
        # JPY has no subunit; this rule will need a currency table if we expand.
        scale = 1 if currency == "JPY" else 100
        return cls(int(round(major * scale)), currency)

    # ---- Arithmetic ---------------------------------------------------------
    def _check(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Currency mismatch: {self.currency} vs {other.currency}"
            )

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount_cents + other.amount_cents, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount_cents - other.amount_cents, self.currency)

    def __mul__(self, factor: int) -> Money:
        if not isinstance(factor, int):
            raise TypeError("Money multiplication is integer-only to avoid rounding bugs")
        return Money(self.amount_cents * factor, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount_cents, self.currency)

    # ---- Comparison ---------------------------------------------------------
    def __lt__(self, other: Money) -> bool:
        self._check(other)
        return self.amount_cents < other.amount_cents

    def __le__(self, other: Money) -> bool:
        self._check(other)
        return self.amount_cents <= other.amount_cents

    def __gt__(self, other: Money) -> bool:
        self._check(other)
        return self.amount_cents > other.amount_cents

    def __ge__(self, other: Money) -> bool:
        self._check(other)
        return self.amount_cents >= other.amount_cents

    # ---- Predicates ---------------------------------------------------------
    @property
    def is_zero(self) -> bool:
        return self.amount_cents == 0

    @property
    def is_positive(self) -> bool:
        return self.amount_cents > 0

    @property
    def is_negative(self) -> bool:
        return self.amount_cents < 0

    # ---- Presentation -------------------------------------------------------
    def __repr__(self) -> str:
        return f"Money({self.amount_cents}, {self.currency!r})"

    def __str__(self) -> str:
        if self.currency == "JPY":
            return f"{self.amount_cents:,} {self.currency}"
        return f"{self.amount_cents / 100:,.2f} {self.currency}"
