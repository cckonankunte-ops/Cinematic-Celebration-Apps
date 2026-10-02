"""Append-only booking audit trail helper.

write_booking_event MUST be called inside the caller's open transaction so the
audit row commits atomically with the state change it records. It flushes but
does NOT commit.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.booking_event import BookingEvent


def write_booking_event(
    db: Session,
    booking_id: int,
    event_type: str,
    *,
    actor_user_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
) -> BookingEvent:
    """Append one booking_events row within the current transaction.

    event_type must be one of: created, accepted, rejected, edited,
    payment_recorded, expired.
    """
    event = BookingEvent(
        booking_id=booking_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(event)
    db.flush()
    return event
