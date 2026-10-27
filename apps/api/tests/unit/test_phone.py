"""Phone normalization tests (pure function, no DB).

Feature: admin-booking-edit, Property 25: Indian-mobile normalization is
canonical and format-invariant
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.phone import normalize_indian_mobile


# --- Concrete examples (R23.4) -------------------------------------------


def test_concrete_examples() -> None:
    assert normalize_indian_mobile("+91 98765 43210") == "9876543210"
    assert normalize_indian_mobile("098765 43210") == "9876543210"
    assert normalize_indian_mobile("9876543210") == "9876543210"


# --- Strategies -----------------------------------------------------------

# Arbitrary strings plus digit-ish strings, so the canonical-range property
# is exercised across both random text and plausible phone-like inputs.
_digitish = st.text(alphabet="0123456789+ -", min_size=0, max_size=20)
_any_raw = st.one_of(st.text(), _digitish)


def _canonical_mobile(draw: st.DrawFn) -> str:
    first = draw(st.integers(min_value=6, max_value=9))
    rest = draw(
        st.lists(st.integers(min_value=0, max_value=9), min_size=9, max_size=9)
    )
    return str(first) + "".join(str(d) for d in rest)


@st.composite
def valid_mobiles(draw: st.DrawFn) -> str:
    return _canonical_mobile(draw)


# --- Property: canonical range -------------------------------------------


@settings(max_examples=100)
@given(raw=_any_raw)
def test_result_is_canonical_or_none(raw: str) -> None:
    """Validates: Requirements 23.2

    The result is either None or a 10-char all-digit string whose first
    char is in "6789".
    """
    result = normalize_indian_mobile(raw)
    if result is not None:
        assert len(result) == 10
        assert result.isdigit()
        assert result[0] in "6789"


# --- Property: format-invariance -----------------------------------------


@settings(max_examples=100)
@given(number=valid_mobiles())
def test_format_invariance(number: str) -> None:
    """Validates: Requirements 23.1, 23.4

    All documented formatting variants of the same mobile normalize to the
    identical canonical 10-digit string.
    """
    spaced = f"{number[:5]} {number[5:]}"
    dashed = f"{number[:5]}-{number[5:]}"
    variants = [
        number,
        f"+91 {number}",
        f"+91{number}",
        f"0{number}",
        f"91{number}",
        spaced,
        dashed,
    ]
    for variant in variants:
        assert normalize_indian_mobile(variant) == number


# --- Malformed inputs -> None --------------------------------------------


def test_malformed_returns_none() -> None:
    assert normalize_indian_mobile("12345") is None
    assert normalize_indian_mobile("1234567890") is None
    assert normalize_indian_mobile("") is None
    assert normalize_indian_mobile("   ") is None
    assert normalize_indian_mobile("abcdefghij") is None
    assert normalize_indian_mobile("98765abcde") is None
    assert normalize_indian_mobile("1" * 50) is None
