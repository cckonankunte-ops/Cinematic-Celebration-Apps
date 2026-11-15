"""Integration tests for review_booking (expired -> pending reinstatement).

Admin-only. Reinstating an expired booking re-checks slot availability: if the
window is still free it returns to 'pending' (and can then be edited/accepted and
re-expire normally); if another active booking now holds an overlapping window it
raises SlotUnavailableError (409). Only 'expired' bookings may be reviewed.
"""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy.orm import Session

from app.core.errors import SlotUnavailableError, ValidationFailedError
from app.core.security import CurrentUser
from app.models.booking import Booking
from app.models.booking_event import BookingEvent
from app.services.booking import review_booking
from sqlalchemy import select
from tests.factories import make_booking, make_location, make_plan, make_slot, make_user

pytestmark = pytest.mark.integration


def _admin(db: Session) -> CurrentUser:
    user = make_user(db, "admin", location_id=None)
    db.commit()
    return CurrentUser(
        id=user.id, username=user.username, role="admin", location_id=None
    )


def test_review_expired_returns_to_pending(db: Session) -> None:
    """An expired booking with a free window reinstates to pending."""
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    booking = make_booking(
        db, location_id=loc.id, plan_id=plan.id, slot_id=slot.id, status="expired"
    )
    db.commit()
    actor = _admin(db)

    result = review_booking(db, booking.id, actor=actor)
    assert result.status == "pending"

    # One audit event captured the expired -> pending transition.
    events = list(
        db.execute(
            select(BookingEvent).where(BookingEvent.booking_id == booking.id)
        ).scalars()
    )
    assert any(
        e.event_type == "edited"
        and (e.new_value or {}).get("action") == "reviewed"
        for e in events
    )


def test_review_rejected_when_slot_taken(db: Session) -> None:
    """If an active booking now holds the overlapping window, review -> 409."""
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id, start_time=time(11, 0), duration_minutes=120)

    # The expired booking carries its window (so overlap can be evaluated).
    expired = make_booking(
        db, location_id=loc.id, plan_id=plan.id, slot_id=slot.id, status="expired"
    )
    expired.start_time = time(11, 0)
    expired.duration_minutes = 120
    # Another ACTIVE booking now occupies the same window on the same date.
    active = make_booking(
        db,
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        status="accepted",
        booking_date=expired.booking_date,
    )
    active.start_time = time(11, 0)
    active.duration_minutes = 120
    db.commit()
    actor = _admin(db)

    with pytest.raises(SlotUnavailableError):
        review_booking(db, expired.id, actor=actor)
    db.rollback()
    assert db.get(Booking, expired.id).status == "expired"


def test_review_non_expired_rejected(db: Session) -> None:
    """Only expired bookings can be reviewed; others raise ValidationFailedError."""
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    booking = make_booking(
        db, location_id=loc.id, plan_id=plan.id, slot_id=slot.id, status="pending"
    )
    db.commit()
    actor = _admin(db)

    with pytest.raises(ValidationFailedError):
        review_booking(db, booking.id, actor=actor)
    db.rollback()
    assert db.get(Booking, booking.id).status == "pending"
