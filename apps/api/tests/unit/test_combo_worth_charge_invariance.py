"""Combo worth is display-only: it never changes what is charged.

The display-only ``compare_at_paise`` must not leak into pricing. The booking
pricing path (``compute_booking_price``) only ever reads a combo's price and its
optional cake/LED baselines, so the charged subtotal/total for a combo selection
must be byte-for-byte identical whether worth is unset, below, equal to, or above
the price.
"""

from __future__ import annotations

from datetime import date

from app.models.combo_item import ComboItem
from app.models.plan import Plan
from app.services.pricing import (
    ComboSelection,
    ValidatedRequest,
    compute_booking_price,
)

_FROM = date(2020, 1, 1)
_TO = date(2099, 12, 31)


def _plan(price_paise: int) -> Plan:
    return Plan(
        id=1,
        location_id=1,
        title="P",
        plan_type=1,
        price_paise=price_paise,
        people_allowed=10,
        max_people_allowed=100,
        extra_guest_paise=0,
        give_discount=False,
        max_discount_paise=0,
        advance_paise=0,
        effective_from=_FROM,
        effective_to=_TO,
    )


def _combo(price: int, compare_at_paise: int | None) -> ComboItem:
    return ComboItem(
        id=1,
        location_id=1,
        name="M",
        description="m",
        price_paise=price,
        object_key="k",
        compare_at_paise=compare_at_paise,
        effective_from=_FROM,
        effective_to=_TO,
    )


def _charge(compare_at_paise: int | None) -> tuple[int, int]:
    req = ValidatedRequest(
        plan=_plan(100000),
        people=4,
        combos=[ComboSelection(item=_combo(30000, compare_at_paise))],
    )
    bd = compute_booking_price(req, is_customer=True)
    return bd.subtotal_paise, bd.total_paise


def test_charge_identical_regardless_of_worth() -> None:
    baseline = _charge(None)
    # Worth below, equal to, and above the price must all charge the same.
    assert _charge(0) == baseline
    assert _charge(20000) == baseline
    assert _charge(30000) == baseline
    assert _charge(100000) == baseline
    # Sanity: the combo (30000) is actually in the charged subtotal.
    assert baseline[0] == 100000 + 30000


def test_booking_request_ignores_client_sent_money() -> None:
    """A client cannot inject worth/savings/totals via the booking request.

    BookingCreate (and ComboSelectionIn) define no money fields; Pydantic v2
    drops unknown keys, so any client-sent money is discarded before it can
    reach the server-authoritative pricing path.
    """
    from datetime import date as _date

    from app.schemas.booking import BookingCreate

    payload = {
        "location_id": 1,
        "plan_id": 1,
        "slot_id": 1,
        "booking_date": _date(2030, 1, 1).isoformat(),
        "booking_name": "Mallory",
        "phone": "9876543210",
        "people": 4,
        "combos": [{"id": 1, "worth_paise": 999999, "savings_paise": 999999}],
        # Injected top-level money that must be ignored.
        "worth_paise": 999999,
        "savings_paise": 999999,
        "subtotal_paise": 1,
        "total_paise": 1,
    }
    model = BookingCreate.model_validate(payload)
    # None of the injected money keys became attributes.
    for leaked in ("worth_paise", "savings_paise", "subtotal_paise", "total_paise"):
        assert not hasattr(model, leaked)
    # The combo selection kept only its id.
    assert model.combos[0].id == 1
    assert not hasattr(model.combos[0], "worth_paise")
    assert not hasattr(model.combos[0], "savings_paise")
