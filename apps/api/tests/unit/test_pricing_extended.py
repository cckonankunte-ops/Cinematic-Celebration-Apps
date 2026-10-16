"""Extended pricing tests: quantities, cake weight, LED, combos, coupons.

Feature: admin-booking-edit — property and unit tests for the extended
server-authoritative pricing algorithm (``services.pricing``).
"""

from __future__ import annotations

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.cake import Cake
from app.models.combo_item import ComboItem
from app.models.plan import Plan
from app.models.special_decor_item import SpecialDecorItem
from app.services.pricing import (
    LED_UNIT_PRICE_PAISE,
    ComboSelection,
    DecorSelection,
    ValidatedCoupon,
    ValidatedRequest,
    compute_booking_price,
    compute_coupon_discount,
    led_letter_count,
)

_FROM = date(2020, 1, 1)
_TO = date(2099, 12, 31)


def _plan(
    *,
    price_paise: int = 0,
    people_allowed: int = 1,
    extra_guest_paise: int = 0,
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
    return Cake(
        id=1, location_id=1, description="C", price_paise=price, object_key="k",
        effective_from=_FROM, effective_to=_TO,
    )


def _decor(id_: int, price: int) -> SpecialDecorItem:
    return SpecialDecorItem(
        id=id_, location_id=1, name="D", description="d", price_paise=price,
        object_key="k", sort_order=id_, effective_from=_FROM, effective_to=_TO,
    )


def _combo(
    id_: int,
    price: int,
    *,
    cake_baseline_paise: int | None = None,
    led_baseline_paise: int | None = None,
) -> ComboItem:
    return ComboItem(
        id=id_, location_id=1, name="M", description="m", price_paise=price,
        object_key="k", effective_from=_FROM, effective_to=_TO,
        cake_baseline_paise=cake_baseline_paise, led_baseline_paise=led_baseline_paise,
    )


# ---------------------------------------------------------------------------
# 4.4 Property 1 — Add-on amount is unit price × quantity.
# ---------------------------------------------------------------------------
@given(
    unit_price=st.integers(0, 500_00),
    quantity=st.integers(1, 20),
)
@settings(max_examples=100)
def test_property_1_decor_amount_is_unit_times_quantity(unit_price, quantity) -> None:
    """Feature: admin-booking-edit, Property 1: Add-on amount is unit price x quantity.

    Validates: Requirements 5.1, 12.1, 14.5
    """
    req = ValidatedRequest(
        plan=_plan(),
        people=1,
        special_decor=[DecorSelection(item=_decor(1, unit_price), quantity=quantity)],
    )
    bd = compute_booking_price(req, is_customer=True)
    decor_lines = [line for line in bd.addon_lines if line.kind == "decor"]
    assert len(decor_lines) == 1
    assert decor_lines[0].amount_paise == unit_price * quantity


# ---------------------------------------------------------------------------
# 4.5 Property 2 — Subtotal composition.
# ---------------------------------------------------------------------------
@given(
    price=st.integers(0, 10_000_00),
    people=st.integers(1, 60),
    people_allowed=st.integers(1, 20),
    extra_rate=st.integers(0, 500_00),
    decor=st.lists(st.tuples(st.integers(0, 300_00), st.integers(1, 10)), max_size=6),
    combo_prices=st.lists(st.integers(0, 300_00), max_size=4),
    cake_price=st.integers(0, 500_00),
    cake_weight=st.integers(1, 8),
)
@settings(max_examples=100)
def test_property_2_subtotal_composition(
    price, people, people_allowed, extra_rate, decor, combo_prices, cake_price, cake_weight
) -> None:
    """Feature: admin-booking-edit, Property 2: Subtotal composition.

    Validates: Requirements 5.2
    """
    req = ValidatedRequest(
        plan=_plan(price_paise=price, people_allowed=people_allowed, extra_guest_paise=extra_rate),
        people=people,
        cake=_cake(cake_price),
        cake_weight_half_kg=cake_weight,
        special_decor=[
            DecorSelection(item=_decor(i + 1, p), quantity=q)
            for i, (p, q) in enumerate(decor)
        ],
        combos=[ComboSelection(item=_combo(i + 1, p)) for i, p in enumerate(combo_prices)],
    )
    bd = compute_booking_price(req, is_customer=True)
    addon_sum = sum(line.amount_paise for line in bd.addon_lines)
    assert bd.subtotal_paise == bd.plan_price_paise + bd.extra_guest_paise + addon_sum


# ---------------------------------------------------------------------------
# 4.6 Property 3 — Total composition, discount clamp, clamp-at-zero.
# ---------------------------------------------------------------------------
@given(
    price=st.integers(0, 10_000_00),
    requested_discount=st.integers(0, 20_000_00),
    max_discount=st.integers(0, 500_00),
    give_discount=st.booleans(),
    food=st.integers(0, 100_00),
    other=st.integers(0, 100_00),
    cleaning=st.integers(0, 100_00),
    coupon_value=st.integers(0, 50_000_00),
)
@settings(max_examples=100)
def test_property_3_total_composition_and_clamp(
    price, requested_discount, max_discount, give_discount, food, other, cleaning, coupon_value
) -> None:
    """Feature: admin-booking-edit, Property 3: Total composition and clamp at zero.

    Validates: Requirements 5.3, 5.4, 20.4, 20.5
    """
    req = ValidatedRequest(
        plan=_plan(
            price_paise=price, people_allowed=4, extra_guest_paise=0,
            give_discount=give_discount, max_discount_paise=max_discount,
        ),
        people=1,
    )
    coupon = ValidatedCoupon(
        code="FLAT", type="flat", value=coupon_value, cap_paise=None,
        percentage_base="total", components=frozenset(),
    )
    bd = compute_booking_price(
        req, discount_paise=requested_discount, food_paise=food,
        other_paise=other, cleaning_paise=cleaning, is_customer=False, coupon=coupon,
    )
    expected_total = max(
        0,
        bd.subtotal_paise + bd.food_paise + bd.other_paise + bd.cleaning_paise
        - bd.discount_paise - bd.coupon_discount_paise,
    )
    assert bd.total_paise == expected_total
    assert bd.total_paise >= 0


# ---------------------------------------------------------------------------
# 4.7 Property 4 — Cake weight pricing.
# ---------------------------------------------------------------------------
@given(
    cake_price=st.integers(0, 500_00),
    weight=st.integers(1, 12),
)
@settings(max_examples=100)
def test_property_4_cake_weight_pricing(cake_price, weight) -> None:
    """Feature: admin-booking-edit, Property 4: Cake weight pricing.

    Validates: Requirements 12.1, 14.3
    """
    req = ValidatedRequest(
        plan=_plan(), people=1, cake=_cake(cake_price), cake_weight_half_kg=weight,
    )
    bd = compute_booking_price(req, is_customer=True)
    cake_lines = [line for line in bd.addon_lines if line.kind == "cake"]
    assert len(cake_lines) == 1
    assert cake_lines[0].amount_paise == cake_price * weight


# ---------------------------------------------------------------------------
# 4.8 Property 5 — LED letter count.
# ---------------------------------------------------------------------------
@given(
    letters=st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", max_size=20),
    noise=st.text(alphabet=" .,!?-_0123456789", max_size=20),
)
@settings(max_examples=100)
def test_property_5_led_letter_count(letters, noise) -> None:
    """Feature: admin-booking-edit, Property 5: LED letter count and charge.

    Validates: Requirements 16.3, 16.5
    """
    # Interleave letters with non-letter noise; count must equal letter count.
    led_name = "".join(a + b for a, b in zip(letters, noise + " " * len(letters)))
    led_name += noise
    expected_count = len(letters)
    assert led_letter_count(led_name) == expected_count

    req = ValidatedRequest(plan=_plan(), people=1, led_name=led_name)
    bd = compute_booking_price(req, is_customer=True)
    led_lines = [line for line in bd.addon_lines if line.kind == "led"]
    if expected_count > 0:
        assert len(led_lines) == 1
        assert led_lines[0].amount_paise == expected_count * LED_UNIT_PRICE_PAISE
    else:
        assert led_lines == []


# ---------------------------------------------------------------------------
# 4.9 Property 6 — Combo line price with floored deltas.
# ---------------------------------------------------------------------------
@given(
    combo_price=st.integers(0, 300_00),
    cake_price=st.integers(0, 500_00),
    cake_weight=st.integers(1, 8),
    cake_baseline=st.integers(0, 500_00),
    led_letters=st.integers(0, 15),
    led_baseline=st.integers(0, 60_00),
)
@settings(max_examples=100)
def test_property_6_combo_floored_deltas(
    combo_price, cake_price, cake_weight, cake_baseline, led_letters, led_baseline
) -> None:
    """Feature: admin-booking-edit, Property 6: Combo line price with floored deltas.

    Validates: Requirements 14.3, 14.4, 15.1, 15.2, 15.3, 15.4, 15.5
    """
    led_name = "A" * led_letters
    req = ValidatedRequest(
        plan=_plan(),
        people=1,
        cake=_cake(cake_price),
        cake_weight_half_kg=cake_weight,
        led_name=led_name,
        combos=[
            ComboSelection(
                item=_combo(
                    1, combo_price,
                    cake_baseline_paise=cake_baseline, led_baseline_paise=led_baseline,
                )
            )
        ],
    )
    bd = compute_booking_price(req, is_customer=True)
    combo_lines = [line for line in bd.addon_lines if line.kind == "combo"]
    assert len(combo_lines) == 1
    cake_weighted = cake_price * cake_weight
    led_charge = led_letters * LED_UNIT_PRICE_PAISE
    expected = (
        combo_price
        + max(0, cake_weighted - cake_baseline)
        + max(0, led_charge - led_baseline)
    )
    assert combo_lines[0].amount_paise == expected


# ---------------------------------------------------------------------------
# 4.10 Property 7 — Cake and LED never double-charged.
# ---------------------------------------------------------------------------
@given(
    combo_price=st.integers(0, 300_00),
    cake_price=st.integers(1, 500_00),
    cake_weight=st.integers(1, 8),
    cake_baseline=st.integers(0, 500_00),
    led_letters=st.integers(1, 15),
    led_baseline=st.integers(0, 60_00),
)
@settings(max_examples=100)
def test_property_7_no_double_charge(
    combo_price, cake_price, cake_weight, cake_baseline, led_letters, led_baseline
) -> None:
    """Feature: admin-booking-edit, Property 7: Cake and LED never double-charged.

    Validates: Requirements 13.7, 14.6, 14.7, 14.8, 14.9, 16.4
    """
    req = ValidatedRequest(
        plan=_plan(),
        people=1,
        cake=_cake(cake_price),
        cake_weight_half_kg=cake_weight,
        led_name="A" * led_letters,
        combos=[
            ComboSelection(
                item=_combo(
                    1, combo_price,
                    cake_baseline_paise=cake_baseline, led_baseline_paise=led_baseline,
                )
            )
        ],
    )
    bd = compute_booking_price(req, is_customer=True)
    # A combo absorbing cake/LED means there are NO standalone cake/led lines.
    assert all(line.kind != "cake" for line in bd.addon_lines)
    assert all(line.kind != "led" for line in bd.addon_lines)
    # Cake/LED contribute only through the single combo line.
    combo_lines = [line for line in bd.addon_lines if line.kind == "combo"]
    assert len(combo_lines) == 1
    cake_weighted = cake_price * cake_weight
    led_charge = led_letters * LED_UNIT_PRICE_PAISE
    expected = (
        combo_price
        + max(0, cake_weighted - cake_baseline)
        + max(0, led_charge - led_baseline)
    )
    assert combo_lines[0].amount_paise == expected


# ---------------------------------------------------------------------------
# 4.11 Property 8 — Coupon discount computation.
# ---------------------------------------------------------------------------
@given(
    flat_value=st.integers(-100_00, 500_00),
    pct=st.integers(0, 100),
    base=st.integers(0, 10_000_00),
    cap=st.one_of(st.none(), st.integers(0, 200_00)),
)
@settings(max_examples=100)
def test_property_8_coupon_discount_computation(flat_value, pct, base, cap) -> None:
    """Feature: admin-booking-edit, Property 8: Coupon discount computation.

    Validates: Requirements 20.3
    """
    # Flat: value clamped at 0, cap irrelevant to flat.
    flat = ValidatedCoupon(
        code="F", type="flat", value=flat_value, cap_paise=cap,
        percentage_base="total", components=frozenset(),
    )
    flat_discount = compute_coupon_discount(
        flat, total_before_coupon=base, plan_price=0, extra_guest=0,
        decor_total=0, combo_total=0, cake_total=0, food=0,
    )
    assert flat_discount == max(0, flat_value)

    # Percentage on 'total': half-up rounding; cap applied AFTER rounding.
    pct_total = ValidatedCoupon(
        code="P", type="percentage", value=pct, cap_paise=cap,
        percentage_base="total", components=frozenset(),
    )
    pct_discount = compute_coupon_discount(
        pct_total, total_before_coupon=base, plan_price=0, extra_guest=0,
        decor_total=0, combo_total=0, cake_total=0, food=0,
    )
    raw = (pct * base + 50) // 100
    expected = min(cap, raw) if cap is not None else raw
    assert pct_discount == expected

    # 'selected_components' base sums only eligible component amounts; 'other'
    # and 'cleaning' are never eligible keys.
    components = frozenset({"plan", "decor", "cake", "food"})
    assert "other" not in components
    assert "cleaning" not in components
    pct_components = ValidatedCoupon(
        code="PC", type="percentage", value=pct, cap_paise=None,
        percentage_base="selected_components", components=components,
    )
    comp_discount = compute_coupon_discount(
        pct_components, total_before_coupon=10_000_00, plan_price=100_00,
        extra_guest=50_00, decor_total=30_00, combo_total=40_00, cake_total=20_00,
        food=10_00,
    )
    selected_base = 100_00 + 30_00 + 20_00 + 10_00  # plan + decor + cake + food
    assert comp_discount == (pct * selected_base + 50) // 100


# ---------------------------------------------------------------------------
# 4.12 Property 9 — Pricing is server-authoritative.
# ---------------------------------------------------------------------------
@given(
    price=st.integers(0, 10_000_00),
    requested_discount=st.integers(0, 20_000_00),
    max_discount=st.integers(0, 500_00),
    coupon_value=st.integers(0, 300_00),
)
@settings(max_examples=100)
def test_property_9_server_authoritative(
    price, requested_discount, max_discount, coupon_value
) -> None:
    """Feature: admin-booking-edit, Property 9: Pricing is server-authoritative.

    Validates: Requirements 5.5, 14.10, 16.6, 20.9
    """
    req = ValidatedRequest(
        plan=_plan(
            price_paise=price, people_allowed=4, extra_guest_paise=0,
            give_discount=True, max_discount_paise=max_discount,
        ),
        people=1,
    )
    coupon = ValidatedCoupon(
        code="F", type="flat", value=coupon_value, cap_paise=None,
        percentage_base="total", components=frozenset(),
    )
    bd = compute_booking_price(
        req, discount_paise=requested_discount, is_customer=True, coupon=coupon,
    )
    # Customer: admin manual discount is forced to 0 regardless of request...
    assert bd.discount_paise == 0
    # ...but a flat coupon still applies.
    assert bd.coupon_discount_paise == coupon_value
    assert bd.total_paise == max(0, price - coupon_value)


# ---------------------------------------------------------------------------
# 4.13 Unit test (mandatory) — quantity-1 backward compatibility.
# ---------------------------------------------------------------------------
def test_quantity_one_backward_compat_single_line_totals() -> None:
    """Quantity-1, weight-1, no combos/LED/coupon reproduces old single-line totals.

    Mandatory tech.md server-side price case.
    Validates: Requirements 5.1, 5.2
    """
    plan = _plan(price_paise=400_000, people_allowed=4, extra_guest_paise=15_000)
    req = ValidatedRequest(
        plan=plan,
        people=7,  # 3 extra guests
        cake=_cake(60_000),
        cake_weight_half_kg=1,
        special_decor=[
            DecorSelection(item=_decor(1, 20_000), quantity=1),
            DecorSelection(item=_decor(2, 10_000), quantity=1),
        ],
    )
    bd = compute_booking_price(req, is_customer=True)

    expected_extra = 3 * 15_000
    expected_subtotal = 400_000 + expected_extra + 60_000 + (20_000 + 10_000)
    assert bd.extra_guest_paise == expected_extra
    assert bd.subtotal_paise == expected_subtotal
    assert bd.coupon_discount_paise == 0
    assert bd.coupon_code is None
    assert bd.total_paise == expected_subtotal
