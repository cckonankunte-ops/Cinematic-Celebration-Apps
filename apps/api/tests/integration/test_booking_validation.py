"""Property tests for booking-request validation.

Feature: cinematic-celebration-system, Property 9: Booking-request validation
rejects invalid items (cross-location, out-of-window/inactive, slot/plan
mismatch, unknown ID, past date, people > max); duplicates are deduped; a valid
request passes and returns the loaded catalog rows.

Validates: Requirements 5.1, 5.2, 5.3
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.core.errors import (
    BookingDateInPastError,
    ItemInvalidError,
    ValidationFailedError,
)
from app.services.booking import validate_booking_request
from tests.factories import (
    FAR_FUTURE,
    FAR_PAST,
    make_cake,
    make_combo,
    make_decor,
    make_location,
    make_plan,
    make_slot,
)

pytestmark = pytest.mark.integration


def _valid_date() -> date:
    return date.today() + timedelta(days=10)


def test_valid_request_passes_and_returns_rows(db: Session) -> None:
    """A fully valid request returns the loaded, de-duplicated catalog rows."""
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot = make_slot(db, plan.id)
    cake = make_cake(db, loc.id)
    decor = make_decor(db, loc.id)
    combo = make_combo(db, loc.id)
    db.flush()

    req = validate_booking_request(
        db,
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        booking_date=_valid_date(),
        people=4,
        cake_id=cake.id,
        special_decor_ids=[decor.id],
        combo_ids=[combo.id],
    )
    assert req.plan.id == plan.id
    assert req.cake is not None and req.cake.id == cake.id
    assert [d.id for d in req.special_decor] == [decor.id]
    assert [c.id for c in req.combos] == [combo.id]


def test_duplicate_addon_ids_are_deduped(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    decor = make_decor(db, loc.id)
    combo = make_combo(db, loc.id)
    db.flush()

    req = validate_booking_request(
        db,
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        booking_date=_valid_date(),
        people=2,
        cake_id=None,
        special_decor_ids=[decor.id, decor.id, decor.id],
        combo_ids=[combo.id, combo.id],
    )
    assert [d.id for d in req.special_decor] == [decor.id]
    assert [c.id for c in req.combos] == [combo.id]


def test_past_date_rejected(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    db.flush()
    with pytest.raises(BookingDateInPastError):
        validate_booking_request(
            db,
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=date.today() - timedelta(days=1),
            people=2,
            cake_id=None,
            special_decor_ids=[],
            combo_ids=[],
        )


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(people=st.integers(min_value=11, max_value=50))
def test_people_over_max_rejected(db: Session, people: int) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot = make_slot(db, plan.id)
    db.flush()
    with pytest.raises(ValidationFailedError):
        validate_booking_request(
            db,
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=_valid_date(),
            people=people,
            cake_id=None,
            special_decor_ids=[],
            combo_ids=[],
        )


def test_cross_location_cake_rejected(db: Session) -> None:
    loc_a = make_location(db, name="A")
    loc_b = make_location(db, name="B")
    plan = make_plan(db, loc_a.id)
    slot = make_slot(db, plan.id)
    foreign_cake = make_cake(db, loc_b.id)
    db.flush()
    with pytest.raises(ItemInvalidError):
        validate_booking_request(
            db,
            location_id=loc_a.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=_valid_date(),
            people=2,
            cake_id=foreign_cake.id,
            special_decor_ids=[],
            combo_ids=[],
        )


def test_cross_location_decor_and_combo_rejected(db: Session) -> None:
    loc_a = make_location(db, name="A")
    loc_b = make_location(db, name="B")
    plan = make_plan(db, loc_a.id)
    slot = make_slot(db, plan.id)
    foreign_decor = make_decor(db, loc_b.id)
    foreign_combo = make_combo(db, loc_b.id)
    db.flush()
    with pytest.raises(ItemInvalidError):
        validate_booking_request(
            db,
            location_id=loc_a.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=_valid_date(),
            people=2,
            cake_id=None,
            special_decor_ids=[foreign_decor.id],
            combo_ids=[],
        )
    with pytest.raises(ItemInvalidError):
        validate_booking_request(
            db,
            location_id=loc_a.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=_valid_date(),
            people=2,
            cake_id=None,
            special_decor_ids=[],
            combo_ids=[foreign_combo.id],
        )


def test_slot_from_different_plan_rejected(db: Session) -> None:
    loc = make_location(db)
    plan_a = make_plan(db, loc.id)
    plan_b = make_plan(db, loc.id)
    slot_b = make_slot(db, plan_b.id)
    db.flush()
    with pytest.raises(ItemInvalidError):
        validate_booking_request(
            db,
            location_id=loc.id,
            plan_id=plan_a.id,
            slot_id=slot_b.id,
            booking_date=_valid_date(),
            people=2,
            cake_id=None,
            special_decor_ids=[],
            combo_ids=[],
        )


def test_unknown_ids_rejected(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    db.flush()
    # Unknown plan.
    with pytest.raises(ItemInvalidError):
        validate_booking_request(
            db,
            location_id=loc.id,
            plan_id=999999,
            slot_id=slot.id,
            booking_date=_valid_date(),
            people=2,
            cake_id=None,
            special_decor_ids=[],
            combo_ids=[],
        )
    # Unknown cake.
    with pytest.raises(ItemInvalidError):
        validate_booking_request(
            db,
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=_valid_date(),
            people=2,
            cake_id=999999,
            special_decor_ids=[],
            combo_ids=[],
        )


def test_inactive_plan_rejected(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id, is_active=False)
    slot = make_slot(db, plan.id)
    db.flush()
    with pytest.raises(ItemInvalidError):
        validate_booking_request(
            db,
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=_valid_date(),
            people=2,
            cake_id=None,
            special_decor_ids=[],
            combo_ids=[],
        )


def test_out_of_window_plan_rejected(db: Session) -> None:
    loc = make_location(db)
    # Plan whose validity window is entirely in the past.
    plan = make_plan(
        db, loc.id, effective_from=FAR_PAST, effective_to=date.today() - timedelta(days=1)
    )
    slot = make_slot(db, plan.id)
    db.flush()
    with pytest.raises(ItemInvalidError):
        validate_booking_request(
            db,
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=_valid_date(),
            people=2,
            cake_id=None,
            special_decor_ids=[],
            combo_ids=[],
        )


def test_out_of_window_slot_rejected(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(
        db,
        plan.id,
        effective_from=FAR_PAST,
        effective_to=date.today() - timedelta(days=1),
    )
    assert slot.effective_to != FAR_FUTURE
    db.flush()
    with pytest.raises(ItemInvalidError):
        validate_booking_request(
            db,
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=_valid_date(),
            people=2,
            cake_id=None,
            special_decor_ids=[],
            combo_ids=[],
        )
