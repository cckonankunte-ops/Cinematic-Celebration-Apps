"""Unit tests: kids pricing + advance resolution (customer-booking-flow-v2).

Pure pricing (no DB). Covers the kid rate (whole-rupee, derived from the plan's
current extra-guest rate), the adults-first guest-allowance rule, the kids=0
regression (reduces to the old extra-guest charge), and the threshold-based
advance resolver.
"""

from __future__ import annotations

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.plan import Plan
from app.services.pricing import (
    AdvanceRuleLike,
    ValidatedRequest,
    compute_booking_price,
    kid_rate_paise,
    resolve_advance_paise,
)

_FROM = date(2020, 1, 1)
_TO = date(2099, 12, 31)


def _plan(
    *,
    price_paise: int = 0,
    people_allowed: int = 2,
    max_people_allowed: int = 100,
    extra_guest_paise: int = 15000,
    kid_price_pct: int = 50,
    advance_paise: int = 50000,
) -> Plan:
    return Plan(
        id=1,
        location_id=1,
        title="P",
        plan_type=1,
        price_paise=price_paise,
        people_allowed=people_allowed,
        max_people_allowed=max_people_allowed,
        extra_guest_paise=extra_guest_paise,
        kid_price_pct=kid_price_pct,
        give_discount=False,
        max_discount_paise=0,
        advance_paise=advance_paise,
        effective_from=_FROM,
        effective_to=_TO,
    )


# --- K1: kid rate is a whole-rupee round-half-up of pct × extra-guest rate ----
def test_k1_kid_rate_is_whole_rupee_half_up() -> None:
    # extra ₹150, 50% -> ₹75 (7500 paise, a whole-rupee multiple of 100).
    assert kid_rate_paise(_plan(extra_guest_paise=15000, kid_price_pct=50)) == 7500
    # extra ₹149 (14900), 50% = 7450 -> rounds to ₹75 (7500), not 7450.
    assert kid_rate_paise(_plan(extra_guest_paise=14900, kid_price_pct=50)) == 7500


@settings(max_examples=100)
@given(
    extra=st.integers(min_value=0, max_value=1_000_00),
    pct=st.sampled_from([0, 50, 100]),
)
def test_k1_kid_rate_is_multiple_of_100(extra: int, pct: int) -> None:
    rate = kid_rate_paise(_plan(extra_guest_paise=extra, kid_price_pct=pct))
    assert rate % 100 == 0  # always a whole rupee
    assert rate >= 0


# --- K2: raising the extra-guest rate raises the kid rate (no frozen price) ---
@settings(max_examples=50)
@given(
    lo=st.integers(min_value=0, max_value=50_000),
    hi=st.integers(min_value=0, max_value=50_000),
)
def test_k2_kid_rate_monotonic_in_extra_guest(lo: int, hi: int) -> None:
    if lo > hi:
        lo, hi = hi, lo
    rate_lo = kid_rate_paise(_plan(extra_guest_paise=lo, kid_price_pct=50))
    rate_hi = kid_rate_paise(_plan(extra_guest_paise=hi, kid_price_pct=50))
    assert rate_hi >= rate_lo


# --- K3: adults-first allowance; only the overflow of each is charged ---------
def _charge(plan: Plan, adults: int, kids: int) -> tuple[int, int]:
    bd = compute_booking_price(
        ValidatedRequest(plan=plan, people=adults, kids=kids), is_customer=False
    )
    return bd.extra_guest_paise, bd.kid_extra_guest_paise


def test_k3_allowance_adults_fill_first() -> None:
    plan = _plan(people_allowed=4, extra_guest_paise=15000, kid_price_pct=50)
    # All within allowance -> no charge.
    assert _charge(plan, adults=2, kids=2) == (0, 0)
    # Adults exactly fill allowance; 2 kids overflow -> 2 × ₹75 = 15000.
    assert _charge(plan, adults=4, kids=2) == (15000, 15000)
    # 5 adults (1 extra) + 1 kid, allowance 4: adult_extra=1 (₹150), kids: allow
    # left=0 -> 1 kid extra (₹75). total=22500, kid portion=7500.
    assert _charge(plan, adults=5, kids=1) == (22500, 7500)
    # 1 adult + 6 kids, allowance 4: allow left=3 -> 3 kid extras × ₹75 = 22500.
    assert _charge(plan, adults=1, kids=6) == (22500, 22500)


# --- K4: pct bounds -----------------------------------------------------------
def test_k4_pct_zero_and_hundred() -> None:
    assert kid_rate_paise(_plan(extra_guest_paise=15000, kid_price_pct=0)) == 0
    # 100% charges kids at the full adult extra-guest rate.
    assert kid_rate_paise(_plan(extra_guest_paise=15000, kid_price_pct=100)) == 15000


# --- K6: all outputs integer paise (no floats leak) ---------------------------
def test_k6_outputs_are_integer_paise() -> None:
    plan = _plan(people_allowed=2, extra_guest_paise=14900, kid_price_pct=50)
    bd = compute_booking_price(
        ValidatedRequest(plan=plan, people=3, kids=2), is_customer=False
    )
    assert isinstance(bd.extra_guest_paise, int)
    assert isinstance(bd.kid_extra_guest_paise, int)
    assert isinstance(bd.total_paise, int)


# --- kids=0 regression: reduces exactly to the old extra-guest charge ---------
@settings(max_examples=50)
@given(
    allowed=st.integers(min_value=1, max_value=10),
    adults=st.integers(min_value=1, max_value=20),
    rate=st.integers(min_value=0, max_value=50_000),
)
def test_kids_zero_matches_legacy_extra_guest(allowed: int, adults: int, rate: int) -> None:
    plan = _plan(people_allowed=allowed, extra_guest_paise=rate, kid_price_pct=50)
    bd = compute_booking_price(
        ValidatedRequest(plan=plan, people=adults, kids=0), is_customer=False
    )
    expected = max(0, adults - allowed) * rate
    assert bd.extra_guest_paise == expected
    assert bd.kid_extra_guest_paise == 0


# --- A1: advance resolution — highest matching threshold wins -----------------
def _rules(*pairs: tuple[int, int]) -> list[AdvanceRuleLike]:
    return [AdvanceRuleLike(min_total_paise=m, advance_paise=a) for m, a in pairs]


def test_a1_highest_matching_threshold_wins() -> None:
    rules = _rules((100000, 50000), (200000, 75000), (250000, 100000))
    # ₹2600 total meets all three -> highest (₹2500) wins -> ₹1000.
    assert resolve_advance_paise(rules, 260000, fallback_paise=12345) == 100000
    # ₹2100 -> ₹2000 band -> ₹750.
    assert resolve_advance_paise(rules, 210000, fallback_paise=12345) == 75000
    # ₹1200 -> ₹1000 band -> ₹500.
    assert resolve_advance_paise(rules, 120000, fallback_paise=12345) == 50000


def test_a1_no_match_and_empty_use_fallback() -> None:
    rules = _rules((100000, 50000))
    # ₹800 below the lowest threshold -> fallback (plan advance).
    assert resolve_advance_paise(rules, 80000, fallback_paise=12345) == 12345
    # No rules at all -> fallback.
    assert resolve_advance_paise([], 500000, fallback_paise=12345) == 12345


def test_a1_advance_flows_into_breakdown() -> None:
    plan = _plan(price_paise=120000, advance_paise=50000)
    rules = _rules((100000, 70000))
    bd = compute_booking_price(
        ValidatedRequest(plan=plan, people=1, kids=0),
        is_customer=False,
        advance_rules=rules,
    )
    # total 120000 meets the 100000 rule -> advance 70000 (not the plan's 50000).
    assert bd.total_paise == 120000
    assert bd.advance_paise == 70000


def test_a1_breakdown_falls_back_to_plan_advance() -> None:
    plan = _plan(price_paise=50000, advance_paise=50000)
    rules = _rules((100000, 70000))
    bd = compute_booking_price(
        ValidatedRequest(plan=plan, people=1, kids=0),
        is_customer=False,
        advance_rules=rules,
    )
    # total 50000 below the only rule -> plan advance fallback.
    assert bd.advance_paise == 50000
