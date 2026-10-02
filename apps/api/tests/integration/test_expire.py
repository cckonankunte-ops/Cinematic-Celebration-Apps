"""Property test for pending-booking expiry.

Feature: cinematic-celebration-system, Property 10: Pending expiry respects
PENDING_HOLD_MINUTES and is idempotent. Only pending bookings created before the
cutoff expire (each with one 'expired' event); newer ones are untouched; a
second immediate run is a no-op (returns 0, adds no events).

Validates: Requirements 6.8
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.models.booking import Booking
from app.models.booking_event import BookingEvent
from app.services.booking import expire_pending_bookings
from tests.factories import make_location, make_plan, make_slot

pytestmark = pytest.mark.integration


def _make_pending_aged(db: Session, loc_id: int, plan_id: int, slot_id: int, minutes_old: int):
    """Create a pending booking with created_at backdated by minutes_old."""
    import secrets

    booking = Booking(
        booking_reference=f"CC-{secrets.token_hex(4)}",
        public_token=secrets.token_urlsafe(12),
        location_id=loc_id,
        plan_id=plan_id,
        slot_id=slot_id,
        booking_date=datetime.now(tz=UTC).date() + timedelta(days=5),
        booking_name="Expiry Test",
        email="exp@example.com",
        people=4,
        plan_price_paise=400000,
        subtotal_paise=400000,
        total_paise=400000,
        advance_paise=50000,
        status="pending",
        created_at=datetime.now(tz=UTC) - timedelta(minutes=minutes_old),
    )
    db.add(booking)
    db.flush()
    return booking


def _expired_event_count(db: Session, booking_id: int) -> int:
    return db.execute(
        select(func.count())
        .select_from(BookingEvent)
        .where(
            BookingEvent.booking_id == booking_id,
            BookingEvent.event_type == "expired",
        )
    ).scalar_one()


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    old_minutes=st.integers(min_value=1, max_value=600),
    new_minutes=st.integers(min_value=0, max_value=1),
)
def test_only_old_pending_expire_and_idempotent(
    db: Session, old_minutes: int, new_minutes: int
) -> None:
    """Older-than-threshold pending expire; newer stay; a second run is a no-op."""
    hold = app_settings.PENDING_HOLD_MINUTES
    loc = make_location(db)
    # Each booking needs its own slot (uq_bookings_active_slot) to coexist.
    plan = make_plan(db, loc.id)
    slot_old = make_slot(db, plan.id, sort_order=1)
    slot_new = make_slot(db, plan.id, sort_order=2)

    old_booking = _make_pending_aged(db, loc.id, plan.id, slot_old.id, hold + old_minutes)
    new_booking = _make_pending_aged(db, loc.id, plan.id, slot_new.id, new_minutes)
    db.commit()

    expired = expire_pending_bookings(db)
    assert expired == 1

    db.refresh(old_booking)
    db.refresh(new_booking)
    assert old_booking.status == "expired"
    assert new_booking.status == "pending"
    assert _expired_event_count(db, old_booking.id) == 1
    assert _expired_event_count(db, new_booking.id) == 0

    # Idempotent: a second immediate run expires nothing and adds no events.
    again = expire_pending_bookings(db)
    assert again == 0
    assert _expired_event_count(db, old_booking.id) == 1
