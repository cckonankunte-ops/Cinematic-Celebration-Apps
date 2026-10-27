"""Invalid catalog item rejection (real Postgres).

Feature: admin-booking-edit, Property 15: Invalid catalog item is rejected.

``validate_booking_request`` raises ITEM_INVALID when a selection references an
unknown item or violates the multiple-baseline rule (more than one cake-baseline
or more than one LED-baseline combo). A single cake-baseline + single
LED-baseline combination is accepted.

Validates: Requirements 7.5
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.errors import ItemInvalidError
from app.schemas.booking import ComboSelectionIn, DecorSelectionIn
from app.services.booking import validate_booking_request
from app.services.pricing import ValidatedRequest
from tests.factories import (
    future_date,
    make_combo,
    make_location,
    make_plan,
    make_slot,
)

pytestmark = pytest.mark.integration


def _seed(db: Session):
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot = make_slot(db, plan.id)
    return loc, plan, slot


def _validate(db, loc, plan, slot, combos):
    return validate_booking_request(
        db,
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        booking_date=future_date(),
        people=4,
        cake_id=None,
        special_decor=[],
        combos=combos,
    )


def test_two_cake_baseline_combos_rejected(db: Session) -> None:
    loc, plan, slot = _seed(db)
    c1 = make_combo(db, loc.id, cake_baseline_paise=40000)
    c2 = make_combo(db, loc.id, cake_baseline_paise=50000)
    db.commit()

    with pytest.raises(ItemInvalidError):
        _validate(
            db, loc, plan, slot,
            [ComboSelectionIn(id=c1.id), ComboSelectionIn(id=c2.id)],
        )


def test_two_led_baseline_combos_rejected(db: Session) -> None:
    loc, plan, slot = _seed(db)
    c1 = make_combo(db, loc.id, led_baseline_paise=20000)
    c2 = make_combo(db, loc.id, led_baseline_paise=30000)
    db.commit()

    with pytest.raises(ItemInvalidError):
        _validate(
            db, loc, plan, slot,
            [ComboSelectionIn(id=c1.id), ComboSelectionIn(id=c2.id)],
        )


def test_single_cake_and_single_led_baseline_accepted(db: Session) -> None:
    """One cake-baseline + one LED-baseline combo is valid (no raise)."""
    loc, plan, slot = _seed(db)
    cake_combo = make_combo(db, loc.id, cake_baseline_paise=40000)
    led_combo = make_combo(db, loc.id, led_baseline_paise=20000)
    db.commit()

    req = _validate(
        db, loc, plan, slot,
        [ComboSelectionIn(id=cake_combo.id), ComboSelectionIn(id=led_combo.id)],
    )
    assert isinstance(req, ValidatedRequest)
    assert len(req.combos) == 2


def test_single_combo_with_both_baselines_accepted(db: Session) -> None:
    """A single combo carrying both cake and LED baselines is valid."""
    loc, plan, slot = _seed(db)
    both = make_combo(db, loc.id, cake_baseline_paise=40000, led_baseline_paise=20000)
    db.commit()

    req = _validate(db, loc, plan, slot, [ComboSelectionIn(id=both.id)])
    assert isinstance(req, ValidatedRequest)
    assert len(req.combos) == 1


def test_unknown_combo_id_rejected(db: Session) -> None:
    loc, plan, slot = _seed(db)
    db.commit()

    with pytest.raises(ItemInvalidError):
        _validate(db, loc, plan, slot, [ComboSelectionIn(id=999_999)])


def test_unknown_decor_id_rejected(db: Session) -> None:
    loc, plan, slot = _seed(db)
    db.commit()

    with pytest.raises(ItemInvalidError):
        validate_booking_request(
            db,
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=future_date(),
            people=4,
            cake_id=None,
            special_decor=[DecorSelectionIn(id=888_888, quantity=1)],
            combos=[],
        )
