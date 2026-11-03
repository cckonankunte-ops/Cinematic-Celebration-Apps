"""Open-mode booking integrity, pricing, validation, and time-rule parity.

Mandatory coverage (tech.md) for the booking-mode-toggle feature. Open-mode
bookings carry start_time + duration_minutes directly (slot_id null). Overlap is
enforced in tests by the service pre-check (the DB exclusion constraint is
migration-only and the harness uses create_all — same limitation as slot mode).
"""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy.orm import Session

from app.core.errors import (
    ItemInvalidError,
    OutsideWorkingHoursError,
    SlotUnavailableError,
    ValidationFailedError,
)
from app.core.security import CurrentUser
from app.models.plan_pricing import PlanPricing
from app.schemas.booking import AdminBookingCreate
from app.services import booking as booking_service
from tests.factories import (
    FAR_FUTURE,
    FAR_PAST,
    future_date,
    make_location,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration


def _admin(db: Session) -> CurrentUser:
    user = make_user(db, "admin", location_id=None)
    return CurrentUser(
        id=user.id, username=user.username, role="admin", location_id=None
    )


def _price(db: Session, plan_id: int, duration: int, price_paise: int = 120000) -> None:
    db.add(
        PlanPricing(
            plan_id=plan_id,
            duration_minutes=duration,
            price_paise=price_paise,
            advance_paise=0,
            effective_from=FAR_PAST,
            effective_to=FAR_FUTURE,
            is_active=True,
        )
    )


def _open_create(
    loc_id: int, plan_id: int, start: time, duration: int, when
) -> AdminBookingCreate:
    return AdminBookingCreate(
        location_id=loc_id,
        plan_id=plan_id,
        start_time=start,
        duration_minutes=duration,
        booking_date=when,
        booking_name="Open",
        phone="9876543210",
        email="o@example.com",
        people=2,
        special_decor=[],
        combos=[],
    )


def _open_location(db: Session):
    loc = make_location(db)
    loc.booking_mode = "open"
    return loc


# --- 6.1 overlap (service pre-check) ---------------------------------------
def test_open_mode_overlap_one_wins(db: Session) -> None:
    admin = _admin(db)
    loc = _open_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    _price(db, plan.id, 60)
    db.commit()

    when = future_date()
    first = booking_service.create_admin_booking(
        db, _open_create(loc.id, plan.id, time(15, 0), 60, when), admin
    )
    assert first.slot_id is None
    # A second window overlapping the first (15:30 within 15:00–16:00+buffer).
    with pytest.raises(SlotUnavailableError):
        booking_service.create_admin_booking(
            db, _open_create(loc.id, plan.id, time(15, 30), 60, when), admin
        )


# --- 6.2 cross-mode overlap -------------------------------------------------
def test_cross_mode_overlap_conflicts(db: Session) -> None:
    """A slot-mode booking and an open-mode booking overlap → the second loses."""
    admin = _admin(db)
    # Slot-mode location with a configured 3-5 PM slot.
    slot_loc = make_location(db)  # booking_mode defaults to 'slot'
    plan = make_plan(db, slot_loc.id, max_people_allowed=10)
    slot = make_slot(
        db, plan.id, start_time=time(15, 0), duration_minutes=120, sort_order=1
    )
    _price(db, plan.id, 120)
    db.commit()

    when = future_date()
    booking_service.create_admin_booking(
        db,
        AdminBookingCreate(
            location_id=slot_loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=when,
            booking_name="Slot",
            phone="9876543210",
            email="s@example.com",
            people=2,
            special_decor=[],
            combos=[],
        ),
        admin,
    )
    # Flip the SAME location to open mode; an overlapping open window conflicts.
    slot_loc.booking_mode = "open"
    db.commit()
    with pytest.raises(SlotUnavailableError):
        booking_service.create_admin_booking(
            db, _open_create(slot_loc.id, plan.id, time(16, 0), 60, when), admin
        )


# --- 6.3 pricing ------------------------------------------------------------
def test_open_mode_duration_drives_price(db: Session) -> None:
    admin = _admin(db)
    loc = _open_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10, price_paise=999999)
    _price(db, plan.id, 60, price_paise=79900)  # 1h = 799
    db.commit()

    booking = booking_service.create_admin_booking(
        db, _open_create(loc.id, plan.id, time(14, 0), 60, future_date()), admin
    )
    # Base price comes from the duration row, not the plan's own price_paise.
    assert booking.plan_price_paise == 79900


def test_open_mode_unpriced_duration_rejected(db: Session) -> None:
    admin = _admin(db)
    loc = _open_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    _price(db, plan.id, 60)  # only 60 is priced
    db.commit()

    with pytest.raises(ItemInvalidError):
        booking_service.create_admin_booking(
            db, _open_create(loc.id, plan.id, time(14, 0), 120, future_date()), admin
        )


# --- 6.4 validation + mode mismatch ----------------------------------------
def test_open_mode_requires_start_and_duration(db: Session) -> None:
    admin = _admin(db)
    loc = _open_location(db)
    plan = make_plan(db, loc.id)
    _price(db, plan.id, 60)
    db.commit()

    # No slot_id and no window → rejected.
    with pytest.raises(ValidationFailedError):
        booking_service.create_admin_booking(
            db,
            AdminBookingCreate(
                location_id=loc.id,
                plan_id=plan.id,
                booking_date=future_date(),
                booking_name="X",
                phone="9876543210",
                email="x@example.com",
                people=2,
                special_decor=[],
                combos=[],
            ),
            admin,
        )


def test_mode_mismatch_slot_payload_against_open_location(db: Session) -> None:
    admin = _admin(db)
    loc = _open_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id, start_time=time(15, 0), duration_minutes=60)
    _price(db, plan.id, 60)
    db.commit()

    # Open-mode location but a slot_id was sent → mode mismatch.
    with pytest.raises(ValidationFailedError):
        booking_service.create_admin_booking(
            db,
            AdminBookingCreate(
                location_id=loc.id,
                plan_id=plan.id,
                slot_id=slot.id,
                booking_date=future_date(),
                booking_name="X",
                phone="9876543210",
                email="x@example.com",
                people=2,
                special_decor=[],
                combos=[],
            ),
            admin,
        )


def test_mode_mismatch_open_payload_against_slot_location(db: Session) -> None:
    admin = _admin(db)
    loc = make_location(db)  # slot mode (default)
    plan = make_plan(db, loc.id)
    _price(db, plan.id, 60)
    db.commit()

    # Slot-mode location but start+duration were sent → mode mismatch.
    with pytest.raises(ValidationFailedError):
        booking_service.create_admin_booking(
            db, _open_create(loc.id, plan.id, time(15, 0), 60, future_date()), admin
        )


# --- 6.5 time-rule parity (open mode) --------------------------------------
def test_open_mode_outside_working_hours_rejected(db: Session) -> None:
    admin = _admin(db)
    loc = _open_location(db)  # opens 10:00, closes 01:00
    plan = make_plan(db, loc.id)
    _price(db, plan.id, 60)
    db.commit()

    # 02:00 start is outside working hours; admins are NOT exempt from hours.
    with pytest.raises(OutsideWorkingHoursError):
        booking_service.create_admin_booking(
            db, _open_create(loc.id, plan.id, time(2, 0), 60, future_date()), admin
        )
