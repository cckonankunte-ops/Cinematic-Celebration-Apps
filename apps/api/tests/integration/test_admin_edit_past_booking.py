"""Admin may edit a past/completed booking; staff may not (real Postgres).

Feature: customer-booking-flow-v2 follow-up. Admins can correct a booking whose
date is already in the past (a "completed" booking); staff remain bound by the
past-date guard and the future-start grace. The window-changing edit path is
what triggers the guard, so the test re-selects the booking's slot.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.errors import BookingDateInPastError
from app.core.security import CurrentUser
from app.schemas.booking import BookingUpdate
from app.services import booking as booking_service
from tests.factories import (
    make_booking,
    make_location,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration


def _user(db: Session, role: str, location_id: int | None) -> CurrentUser:
    u = make_user(db, role, location_id=location_id)
    return CurrentUser(
        id=u.id, username=u.username, role=role, location_id=location_id
    )


def _past_accepted_booking(db: Session):
    """Seed an accepted booking whose date is in the past (a completed party)."""
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot = make_slot(db, plan.id)
    past = date.today() - timedelta(days=5)
    booking = make_booking(
        db,
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        status="accepted",
        booking_date=past,
        people=4,
    )
    db.commit()
    return booking, slot


def test_admin_can_edit_a_past_booking_window(db: Session) -> None:
    """Admin re-selects the slot on a past-dated booking → succeeds."""
    booking, slot = _past_accepted_booking(db)
    admin = _user(db, "admin", location_id=None)  # admin = all locations

    # Re-selecting the slot sets window_changed=True, which hits the past-date
    # guard; an admin is exempt and the edit goes through.
    updated = booking_service.update_booking(
        db, booking.id, BookingUpdate(slot_id=slot.id, people=6), admin
    )
    assert updated.people == 6
    db.refresh(booking)
    assert booking.people == 6


def test_staff_cannot_edit_a_past_booking_window(db: Session) -> None:
    """Staff making the same past-dated window edit → BookingDateInPastError."""
    booking, slot = _past_accepted_booking(db)
    # Staff must be scoped to the booking's location or access is denied first;
    # scope them correctly so the past-date guard is what actually blocks them.
    staff = _user(db, "staff", location_id=booking.location_id)

    with pytest.raises(BookingDateInPastError):
        booking_service.update_booking(
            db, booking.id, BookingUpdate(slot_id=slot.id, people=6), staff
        )
