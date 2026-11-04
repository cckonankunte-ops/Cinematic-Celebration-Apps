"""Unit tests for the display-only combo savings helper.

``combo_savings_paise(price, worth)`` must return ``max(0, worth - price)`` and
0 when worth is None. It is display-only and never affects what is charged.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.services.catalog import combo_savings_paise


# --- Concrete examples ---------------------------------------------------------
def test_worth_greater_than_price_yields_positive_saving() -> None:
    assert combo_savings_paise(70000, 100000) == 30000


def test_worth_equal_to_price_yields_zero() -> None:
    assert combo_savings_paise(70000, 70000) == 0


def test_worth_below_price_yields_zero_not_negative() -> None:
    assert combo_savings_paise(70000, 50000) == 0


def test_worth_none_yields_zero() -> None:
    assert combo_savings_paise(70000, None) == 0


# --- Property: never negative, matches max(0, worth - price) -------------------
@given(
    price=st.integers(min_value=0, max_value=10_000_00),
    worth=st.one_of(st.none(), st.integers(min_value=0, max_value=10_000_00)),
)
def test_savings_never_negative_and_matches_formula(
    price: int, worth: int | None
) -> None:
    result = combo_savings_paise(price, worth)
    assert result >= 0
    expected = 0 if worth is None else max(0, worth - price)
    assert result == expected
