"""Money — invariants and arithmetic.

Property-based tests guard the most dangerous corners: cross-currency
arithmetic must always raise; same-currency addition must be commutative
and associative; ordering must be total within a currency.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from reflow.core.types import CurrencyMismatchError, Money

pytestmark = pytest.mark.unit

CURRENCIES = st.sampled_from(["USD", "EUR", "GBP", "INR", "JPY"])
amount_st = st.integers(min_value=-10**12, max_value=10**12)


def money(amount: int, currency: str = "USD") -> Money:
    return Money(amount, currency)


class TestConstruction:
    def test_zero_constructs(self) -> None:
        assert Money.zero("USD") == Money(0, "USD")

    def test_rejects_unsupported_currency(self) -> None:
        with pytest.raises(ValueError, match="Unsupported currency"):
            Money(100, "XYZ")

    def test_rejects_non_int_amount(self) -> None:
        with pytest.raises(TypeError):
            Money(1.5, "USD")  # type: ignore[arg-type]

    def test_from_major_units_usd(self) -> None:
        assert Money.from_major_units(10, "USD").amount_cents == 1000

    def test_from_major_units_jpy_has_no_subunit(self) -> None:
        # JPY is whole-yen only — minor units would be a bug.
        assert Money.from_major_units(1000, "JPY").amount_cents == 1000


class TestArithmetic:
    def test_same_currency_addition_commutative(self) -> None:
        a = money(100)
        b = money(250)
        assert a + b == b + a

    def test_cross_currency_addition_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            money(100, "USD") + money(100, "EUR")

    def test_subtraction(self) -> None:
        assert money(300) - money(100) == money(200)

    def test_integer_multiplication(self) -> None:
        assert money(100) * 3 == money(300)

    def test_float_multiplication_is_a_bug(self) -> None:
        with pytest.raises(TypeError):
            _ = money(100) * 1.5  # type: ignore[operator]

    def test_negation(self) -> None:
        assert -money(100) == money(-100)


class TestComparison:
    def test_total_ordering_within_currency(self) -> None:
        assert money(1) < money(2) < money(3)
        assert money(3) > money(2) > money(1)

    def test_cross_currency_comparison_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            _ = money(100, "USD") < money(100, "EUR")


class TestPredicates:
    def test_is_zero(self) -> None:
        assert money(0).is_zero

    def test_is_positive(self) -> None:
        assert money(1).is_positive

    def test_is_negative(self) -> None:
        assert money(-1).is_negative


class TestPropertyBased:
    @given(a=amount_st, b=amount_st, currency=CURRENCIES)
    def test_addition_associative(self, a: int, b: int, currency: str) -> None:
        x, y = Money(a, currency), Money(b, currency)
        # (x + y) + zero == x + (y + zero)
        z = Money.zero(currency)
        assert (x + y) + z == x + (y + z)

    @given(a=amount_st, currency=CURRENCIES)
    def test_double_negation_is_identity(self, a: int, currency: str) -> None:
        m = Money(a, currency)
        assert -(-m) == m

    @given(a=amount_st, currency=CURRENCIES)
    def test_zero_is_additive_identity(self, a: int, currency: str) -> None:
        m = Money(a, currency)
        z = Money.zero(currency)
        assert m + z == m
        assert z + m == m
