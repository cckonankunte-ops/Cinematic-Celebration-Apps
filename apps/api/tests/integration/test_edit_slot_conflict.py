"""Slot conflict + self-exclusion integration test (real Postgres).

Feature: admin-booking-edit, Property 16: Slot conflict with self-exclusion.

The DB partial unique index ``uq_bookings_active_slot`` on
(location_id, plan_id, slot_id, booking_date) WHERE status IN
('pending','accepted') prevents two ACTIVE bookings from holding the same slot.
Editing a booking must NOT collide with its OWN active row (self-exclusion),
while a second active insert on that exact key must still be rejected.

Validates: Requirements 8.1, 8.2, 8.3
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.errors import SlotUnavailableError
from app.core.security import CurrentUser
from app.schemas.booking import AdminBookingCreate, BookingUpdate
from app.services import booking as booking_service
from tests.factories import future_date, make_location, make_plan, make_slot

pytestmark = pytest.mark.integration


def _admin() -> CurrentUser:
    return CurrentUser(id=1, username="admin", role="admin", location_id=None)


def _admin_create(location_id: int, plan_id: int, slot_id: int, when) -> AdminBookingCreate:
    return AdminBookingCreate(
        location_id=location_id,
        plan_id=plan_id,
        slot_id=slot_id,
        booking_date=when,
        booking_name="X",
        phone="9876543210",
        email="x@example.com",
        people=4,
        special_decor=[],
        combos=[],
    )


def test_edit_does_not_conflict_with_itself(db: Session) -> None:
    """Editing a booking (change people) does NOT collide with its own active row."""
    admin = _admin()
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot_a = make_slot(db, plan.id, description="9-12", sort_order=1)
    slot_b = make_slot(db, plan.id, description="12-3", sort_order=2)
    db.commit()

    when = future_date()
    booking1 = booking_service.create_admin_booking(
        db, _admin_create(loc.id, plan.id, slot_a.id, when), admin
    )
    booking2 = booking_service.create_admin_booking(
        db, _admin_create(loc.id, plan.id, slot_b.id, when), admin
    )
    assert booking1.status == "accepted"
    assert booking2.status == "accepted"

    # Self-exclusion: re-pricing booking1 touches its own active (loc, plan,
    # slot, date) row, which must NOT trigger a slot conflict.
    updated = booking_service.update_booking(
        db, booking1.id, BookingUpdate(people=5), admin
    )
    assert updated.people == 5

    db.refresh(booking1)
    assert booking1.people == 5
    # booking2 is untouched and still on its own slot.
    db.refresh(booking2)
    assert booking2.slot_id == slot_b.id


def test_second_active_booking_on_same_slot_rejected(db: Session) -> None:
    """A second active insert on an identical (loc, plan, slot, date) key -> 409."""
    admin = _admin()
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot_a = make_slot(db, plan.id)
    db.commit()

    when = future_date()
    booking1 = booking_service.create_admin_booking(
        db, _admin_create(loc.id, plan.id, slot_a.id, when), admin
    )
    assert booking1.status == "accepted"

    # Duplicate active hold on booking1's exact slot/date -> SlotUnavailableError.
    with pytest.raises(SlotUnavailableError):
        booking_service.create_admin_booking(
            db, _admin_create(loc.id, plan.id, slot_a.id, when), admin
        )

    # Nothing extra persisted: only booking1 holds that slot/date.
    from app.models.booking import Booking

    active = (
        db.query(Booking)
        .filter(
            Booking.location_id == loc.id,
            Booking.plan_id == plan.id,
            Booking.slot_id == slot_a.id,
            Booking.booking_date == when,
            Booking.status.in_(("pending", "accepted")),
        )
        .all()
    )
    assert len(active) == 1
    assert active[0].id == booking1.id
