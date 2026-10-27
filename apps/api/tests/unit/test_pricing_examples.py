"""Worked pricing examples (mandatory tech.md server-side price cases).

Pure unit tests for ``services.pricing`` — NO database. These lock down the
concrete combo/cake/LED/coupon arithmetic described in Requirement 15's worked
examples so a regression in the delta/clamp math is caught immediately.
"""

from __future__ import annotations

from datetime import date

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


def _combo_line_amount(bd) -> int:
    """Return the single combo add-on line amount (asserts exactly one)."""
    combo_lines = [line for line in bd.addon_lines if line.kind == "combo"]
    assert len(combo_lines) == 1
    return combo_lines[0].amount_paise


# A plan that contributes nothing: price 0, large people_allowed, extra 0. Only
# the combo/cake line adds to the total, so we can read the example arithmetic.
def _free_plan() -> Plan:
    return _plan(price_paise=0, people_allowed=1000, extra_guest_paise=0)


# ---------------------------------------------------------------------------
# Requirement 15 worked examples — combo lines.
# ---------------------------------------------------------------------------
def test_example_combo1_led_at_baseline() -> None:
    """Combo1: price 70000, led_baseline 20000, no cake. LED 'ARUNA' (5) -> 70000."""
    req = ValidatedRequest(
        plan=_free_plan(),
        people=1,
        led_name="ARUNA",  # 5 letters -> 5 x 4000 = 20000 == baseline, delta 0
        combos=[ComboSelection(item=_combo(1, 70000, led_baseline_paise=20000))],
    )
    bd = compute_booking_price(req, is_customer=True)
    assert led_letter_count("ARUNA") == 5
    assert _combo_line_amount(bd) == 70000


def test_example_combo1_led_above_baseline() -> None:
    """Combo1 + LED 'SANJAY' (6): 70000 + (24000 - 20000) = 74000."""
    req = ValidatedRequest(
        plan=_free_plan(),
        people=1,
        led_name="SANJAY",  # 6 letters -> 24000; delta 4000
        combos=[ComboSelection(item=_combo(1, 70000, led_baseline_paise=20000))],
    )
    bd = compute_booking_price(req, is_customer=True)
    assert led_letter_count("SANJAY") == 6
    assert _combo_line_amount(bd) == 74000


def test_example_combo2_led_below_baseline_floored() -> None:
    """Combo2: price 90000, led_baseline 20000, no cake. LED <=5 letters -> 90000."""
    req = ValidatedRequest(
        plan=_free_plan(),
        people=1,
        led_name="ARUNA",  # 5 letters -> 20000; delta max(0, 20000-20000)=0
        combos=[ComboSelection(item=_combo(2, 90000, led_baseline_paise=20000))],
    )
    bd = compute_booking_price(req, is_customer=True)
    assert _combo_line_amount(bd) == 90000


def test_example_combo3_cake_half_kg_plus_led() -> None:
    """Combo3: price 110000, cake_baseline 40000, led_baseline 20000.

    cake base 50000 @ 0.5kg (weight_half_kg=1) + LED 'ARUNA':
      110000 + max(0, 50000-40000) + max(0, 20000-20000) = 120000.
    The combo absorbs the cake, so there is NO standalone cake line.
    """
    req = ValidatedRequest(
        plan=_free_plan(),
        people=1,
        cake=_cake(50000),
        cake_weight_half_kg=1,
        led_name="ARUNA",
        combos=[
            ComboSelection(
                item=_combo(3, 110000, cake_baseline_paise=40000, led_baseline_paise=20000)
            )
        ],
    )
    bd = compute_booking_price(req, is_customer=True)
    assert all(line.kind != "cake" for line in bd.addon_lines)
    assert _combo_line_amount(bd) == 120000


def test_example_combo3_cake_one_kg_plus_led() -> None:
    """Combo3 same cake @ 1.0kg (weight_half_kg=2 -> weighted 100000) + 'ARUNA':
      110000 + max(0, 100000-40000) + 0 = 170000. No standalone cake line.
    """
    req = ValidatedRequest(
        plan=_free_plan(),
        people=1,
        cake=_cake(50000),
        cake_weight_half_kg=2,  # weighted 100000
        led_name="ARUNA",
        combos=[
            ComboSelection(
                item=_combo(3, 110000, cake_baseline_paise=40000, led_baseline_paise=20000)
            )
        ],
    )
    bd = compute_booking_price(req, is_customer=True)
    assert all(line.kind != "cake" for line in bd.addon_lines)
    assert _combo_line_amount(bd) == 170000


# ---------------------------------------------------------------------------
# LED letter count worked example.
# ---------------------------------------------------------------------------
def test_example_led_letter_count_ignores_space() -> None:
    """'HAPPY BIRTHDAY' has 13 letters (the space is ignored)."""
    assert led_letter_count("HAPPY BIRTHDAY") == 13


# ---------------------------------------------------------------------------
# Standalone cake weight examples (no combo absorbs the cake).
# ---------------------------------------------------------------------------
def test_example_standalone_cake_weight_multiples() -> None:
    """Cake base 50000 at 0.5/1.0/1.5kg -> standalone cake line 50000/100000/150000."""
    for weight_half_kg, expected in ((1, 50000), (2, 100000), (3, 150000)):
        req = ValidatedRequest(
            plan=_free_plan(),
            people=1,
            cake=_cake(50000),
            cake_weight_half_kg=weight_half_kg,
        )
        bd = compute_booking_price(req, is_customer=True)
        cake_lines = [line for line in bd.addon_lines if line.kind == "cake"]
        assert len(cake_lines) == 1
        assert cake_lines[0].amount_paise == expected


# ---------------------------------------------------------------------------
# Coupon larger than total clamps the final total to 0.
# ---------------------------------------------------------------------------
def test_example_coupon_larger_than_total_clamps_to_zero() -> None:
    """A flat coupon far exceeding the total clamps the final total to 0."""
    plan = _plan(price_paise=100000, people_allowed=1, extra_guest_paise=0)
    req = ValidatedRequest(plan=plan, people=1)
    coupon = ValidatedCoupon(
        code="HUGE", type="flat", value=99_999_999, cap_paise=None,
        percentage_base="total", components=frozenset(),
    )
    bd = compute_booking_price(req, is_customer=False, coupon=coupon)
    assert bd.total_paise == 0


def test_led_unit_price_constant() -> None:
    """The single documented LED rate is ₹40/letter (4000 paise)."""
    assert LED_UNIT_PRICE_PAISE == 4000


def test_example_standalone_decor_line_unit_times_quantity() -> None:
    """A standalone decor selection prices as unit x quantity (20000 x 3)."""
    req = ValidatedRequest(
        plan=_free_plan(),
        people=1,
        special_decor=[DecorSelection(item=_decor(1, 20000), quantity=3)],
    )
    bd = compute_booking_price(req, is_customer=True)
    decor_lines = [line for line in bd.addon_lines if line.kind == "decor"]
    assert len(decor_lines) == 1
    assert decor_lines[0].amount_paise == 60000


# ---------------------------------------------------------------------------
# Combo line component fields (combo_base / cake_upgrade / led_upgrade).
# ---------------------------------------------------------------------------
def test_combo_line_exposes_upgrade_components() -> None:
    """A combo line carries its base + floored cake/LED upgrade deltas.

    Combo price 70000, cake_baseline 40000, led_baseline 20000; cake base 60000
    at 0.5kg (weighted 60000 -> cake_upgrade 20000) and LED 'ARUNA' (5 letters
    -> 20000 == baseline, led_upgrade 0). The single combo line should report
    combo_base_paise=70000, cake_upgrade_paise=20000, led_upgrade_paise=0, and
    amount_paise=90000 (== base + cake + led).
    """
    req = ValidatedRequest(
        plan=_free_plan(),
        people=1,
        cake=_cake(60000),
        cake_weight_half_kg=1,  # weighted 60000; upgrade max(0, 60000-40000)=20000
        led_name="ARUNA",  # 5 letters -> 20000 == baseline; upgrade 0
        combos=[
            ComboSelection(
                item=_combo(1, 70000, cake_baseline_paise=40000, led_baseline_paise=20000)
            )
        ],
    )
    bd = compute_booking_price(req, is_customer=True)
    combo_lines = [line for line in bd.addon_lines if line.kind == "combo"]
    assert len(combo_lines) == 1
    line = combo_lines[0]
    assert line.combo_base_paise == 70000
    assert line.cake_upgrade_paise == 20000
    assert line.led_upgrade_paise == 0
    assert line.amount_paise == 90000
