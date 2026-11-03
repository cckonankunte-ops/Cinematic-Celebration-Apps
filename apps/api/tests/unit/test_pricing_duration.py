"""Unit tests for duration-based base pricing (R11).

Pure ``services.pricing`` tests — NO database. Verify the ``base_price_paise``
override replaces the plan's price while extra-guest/add-ons stack on top, and
that omitting it falls back to the plan price.
"""

from __future__ import annotations

from datetime import date

from app.models.plan import Plan
from app.services.pricing import ValidatedRequest, compute_booking_price

_FROM = date(2020, 1, 1)
_TO = date(2099, 12, 31)


def _plan(price_paise: int, *, people_allowed: int = 2, extra_guest_paise: int = 0) -> Plan:
    return Plan(
        id=1,
        location_id=1,
        title="P",
        plan_type=1,
        price_paise=price_paise,
        people_allowed=people_allowed,
        max_people_allowed=100,
        extra_guest_paise=extra_guest_paise,
        give_discount=False,
        max_discount_paise=0,
        advance_paise=0,
        effective_from=_FROM,
        effective_to=_TO,
    )


def _req(plan: Plan, people: int = 2) -> ValidatedRequest:
    return ValidatedRequest(plan=plan, people=people)


def test_override_sets_base_price() -> None:
    # Plan's own price is the 2h price (119900); override to the 1h price (79900).
    plan = _plan(119900)
    one_hour = compute_booking_price(
        _req(plan), is_customer=True, base_price_paise=79900
    )
    assert one_hour.plan_price_paise == 79900
    assert one_hour.total_paise == 79900  # no add-ons/extra-guest


def test_fallback_to_plan_price_when_no_override() -> None:
    plan = _plan(119900)
    two_hour = compute_booking_price(_req(plan), is_customer=True)
    assert two_hour.plan_price_paise == 119900
    assert two_hour.total_paise == 119900


def _total(plan: Plan, base: int, people: int = 2) -> int:
    return compute_booking_price(
        _req(plan, people), is_customer=True, base_price_paise=base
    ).total_paise


def test_example_prices_plan1_and_plan2() -> None:
    # Plan 1: 1h=799, 2h=1199 (₹ -> paise). Plan 2: 1h=1499, 2h=1999.
    p1 = _plan(119900, people_allowed=2)
    assert _total(p1, 79900) == 79900
    assert _total(p1, 119900) == 119900

    p2 = _plan(199900, people_allowed=6)
    assert _total(p2, 149900, people=6) == 149900
    assert _total(p2, 199900, people=6) == 199900


def test_extra_guest_stacks_on_duration_base() -> None:
    # 1h base 79900, 2 included, extra-guest 15000; 4 people => +2*15000.
    plan = _plan(119900, people_allowed=2, extra_guest_paise=15000)
    bd = compute_booking_price(
        _req(plan, people=4), is_customer=True, base_price_paise=79900
    )
    assert bd.plan_price_paise == 79900
    assert bd.extra_guest_paise == 30000
    assert bd.total_paise == 109900
