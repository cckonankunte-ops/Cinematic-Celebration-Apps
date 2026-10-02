"""Pricing tests (pure functions, no DB).

Feature: cinematic-celebration-system, Property 4: Server-side pricing is
authoritative and correct.
"""

from __future__ import annotations

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.cake import Cake
from app.models.combo_item import ComboItem
from app.models.plan import Plan
from app.models.special_decor_item import SpecialDecorItem
from app.services.pricing import ValidatedRequest, compute_booking_price

_FROM = date(2020, 1, 1)
_TO = date(2099, 12, 31)


def _plan(
    *,
    price_paise: int,
    people_allowed: int,
    extra_guest_paise: int,
    give_discount: bool = False,
    max_discount_paise: int = 0,
) -> Plan:
    return Plan(
        id=1,
        location_id=1,
        title="P",
        plan_type=1,
        price_paise=price_paise,
        people_allowed=people_allowed,
        max_people_allowed=100,
        extra_guest_paise=extra_guest_paise,
        give_discount=give_discount,
        max_discount_paise=max_discount_paise,
        advance_paise=0,
        effective_from=_FROM,
        effective_to=_TO,
    )


def _cake(price: int) -> Cake:
    return Cake(id=1, location_id=1, description="C", price_paise=price, object_key="k",
                effective_from=_FROM, effective_to=_TO)


def _decor(id_: int, price: int) -> SpecialDecorItem:
    return SpecialDecorItem(id=id_, location_id=1, name="D", description="d",
                            price_paise=price, object_key="k", sort_order=id_,
                            effective_from=_FROM, effective_to=_TO)


def _combo(id_: int, price: int) -> ComboItem:
    return ComboItem(id=id_, location_id=1, name="M", description="m",
                     price_paise=price, object_key="k",
                     effective_from=_FROM, effective_to=_TO)


@given(
    price=st.integers(0, 10_000_00),
    people=st.integers(1, 60),
    people_allowed=st.integers(1, 20),
    extra_rate=st.integers(0, 500_00),
    cake_price=st.integers(0, 500_00),
    decor_prices=st.lists(st.integers(0, 300_00), max_size=6),
    combo_prices=st.lists(st.integers(0, 300_00), max_size=4),
    food=st.integers(0, 100_00),
    other=st.integers(0, 100_00),
    cleaning=st.integers(0, 100_00),
)
@settings(max_examples=100)
def test_customer_pricing_formula(
    price, people, people_allowed, extra_rate, cake_price,
    decor_prices, combo_prices, food, other, cleaning,
) -> None:
    """Property 4 (customer): total matches the formula; discount always 0."""
    req = ValidatedRequest(
        plan=_plan(price_paise=price, people_allowed=people_allowed, extra_guest_paise=extra_rate),
        people=people,
        cake=_cake(cake_price),
        special_decor=[_decor(i + 1, p) for i, p in enumerate(decor_prices)],
        combos=[_combo(i + 1, p) for i, p in enumerate(combo_prices)],
    )
    bd = compute_booking_price(
        req, discount_paise=9_999_99, food_paise=food, other_paise=other,
        cleaning_paise=cleaning, is_customer=True,
    )
    expected_extra = max(0, people - people_allowed) * extra_rate
    expected_subtotal = price + expected_extra + cake_price + sum(decor_prices) + sum(combo_prices)
    assert bd.discount_paise == 0  # customers never get a discount
    assert bd.subtotal_paise == expected_subtotal
    assert bd.total_paise == expected_subtotal + food + other + cleaning


@given(
    price=st.integers(0, 10_000_00),
    requested_discount=st.integers(0, 10_000_00),
    max_discount=st.integers(0, 500_00),
    give_discount=st.booleans(),
)
@settings(max_examples=100)
def test_admin_discount_clamped_and_gated(
    price, requested_discount, max_discount, give_discount
) -> None:
    """Property 4 (admin): discount = min(requested, max) if give_discount else 0."""
    req = ValidatedRequest(
        plan=_plan(
            price_paise=price, people_allowed=4, extra_guest_paise=0,
            give_discount=give_discount, max_discount_paise=max_discount,
        ),
        people=1,
    )
    bd = compute_booking_price(req, discount_paise=requested_discount, is_customer=False)
    expected = min(requested_discount, max_discount) if give_discount else 0
    assert bd.discount_paise == expected
    assert bd.total_paise == price - expected


def test_no_extra_guest_when_under_allowance() -> None:
    req = ValidatedRequest(
        plan=_plan(price_paise=400000, people_allowed=4, extra_guest_paise=15000),
        people=3,
    )
    bd = compute_booking_price(req, is_customer=True)
    assert bd.extra_guest_paise == 0
    assert bd.total_paise == 400000


def test_extra_guests_charged_per_head() -> None:
    req = ValidatedRequest(
        plan=_plan(price_paise=400000, people_allowed=4, extra_guest_paise=15000),
        people=7,
    )
    bd = compute_booking_price(req, is_customer=True)
    assert bd.extra_guest_paise == 3 * 15000
    assert bd.total_paise == 400000 + 45000


def test_zero_addons() -> None:
    plan = _plan(price_paise=250000, people_allowed=4, extra_guest_paise=0)
    req = ValidatedRequest(plan=plan, people=4)
    bd = compute_booking_price(req, is_customer=True)
    assert bd.addon_lines == []
    assert bd.total_paise == 250000


def test_addon_lines_snapshot_names_and_prices() -> None:
    req = ValidatedRequest(
        plan=_plan(price_paise=100000, people_allowed=4, extra_guest_paise=0),
        people=4,
        cake=_cake(60000),
        special_decor=[_decor(1, 20000)],
        combos=[_combo(1, 30000)],
    )
    bd = compute_booking_price(req, is_customer=True)
    kinds = {line.kind for line in bd.addon_lines}
    assert kinds == {"cake", "decor", "combo"}
    assert bd.subtotal_paise == 100000 + 60000 + 20000 + 30000
