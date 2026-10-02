"""Property test for booking-event audit completeness.

Feature: cinematic-celebration-system, Property 8: Every state change writes
exactly one booking_event. For a random valid sequence of state-changing
operations applied to a booking, the number of booking_events rows equals the
number of successful operations, and each row carries the right event_type.

Validates: Requirements 6.2, 6.6, 6.7, 7.1, 7.5, 7.6
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import CurrentUser
from app.models.booking_event import BookingEvent
from app.schemas.booking import AdminBookingCreate, BookingUpdate
from app.schemas.payment import PaymentCreate
from app.services import payments as payments_service
from app.services.booking import (
    accept_booking,
    create_admin_booking,
    reject_booking,
    update_booking,
)
from tests.factories import (
    future_date,
    make_location,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration

_ADVANCE = 50000

# Operations applied after create; each is a single state change -> one event.
_OPS = st.lists(
    st.sampled_from(["payment", "edit", "reject"]),
    min_size=0,
    max_size=5,
)


def _event_counts(db: Session, booking_id: int) -> tuple[int, dict[str, int]]:
    rows = list(
        db.execute(
            select(BookingEvent.event_type).where(BookingEvent.booking_id == booking_id)
        ).scalars()
    )
    by_type: dict[str, int] = {}
    for t in rows:
        by_type[t] = by_type.get(t, 0) + 1
    return len(rows), by_type


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(ops=_OPS)
def test_event_count_equals_state_changes(db: Session, ops: list[str]) -> None:
    """Each successful state change adds exactly one booking_events row."""
    loc = make_location(db)
    plan = make_plan(db, loc.id, advance_paise=_ADVANCE)
    slot = make_slot(db, plan.id)
    db.commit()
    user = make_user(db, "admin", location_id=None)
    db.commit()
    actor = CurrentUser(id=user.id, username=user.username, role="admin", location_id=None)

    # create_admin_booking -> status accepted + one 'created' event.
    booking = create_admin_booking(
        db,
        AdminBookingCreate(
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=future_date(),
            booking_name="Audit Test",
            email="audit@example.com",
            people=4,
        ),
        actor,
    )
    expected = 1  # created
    expected_types: dict[str, int] = {"created": 1}
    terminal = False  # rejected bookings get no further ops

    for op in ops:
        if terminal:
            break
        if op == "payment":
            payments_service.record_payment(
                db, booking.id, PaymentCreate(method="upi", amount_paise=10000), actor
            )
            expected += 1
            expected_types["payment_recorded"] = expected_types.get("payment_recorded", 0) + 1
        elif op == "edit":
            update_booking(db, booking.id, BookingUpdate(people=5), actor)
            expected += 1
            expected_types["edited"] = expected_types.get("edited", 0) + 1
        elif op == "reject":
            reject_booking(db, booking.id, actor=actor)
            expected += 1
            expected_types["rejected"] = expected_types.get("rejected", 0) + 1
            terminal = True

    total, by_type = _event_counts(db, booking.id)
    assert total == expected
    assert by_type == expected_types


def test_accept_writes_single_accepted_event(db: Session) -> None:
    """Accepting a pending booking writes exactly one 'accepted' event."""
    loc = make_location(db)
    plan = make_plan(db, loc.id, advance_paise=_ADVANCE)
    slot = make_slot(db, plan.id)
    db.commit()
    user = make_user(db, "admin", location_id=None)
    db.commit()
    actor = CurrentUser(id=user.id, username=user.username, role="admin", location_id=None)

    from tests.factories import make_booking

    booking = make_booking(
        db,
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        status="pending",
        advance_paise=_ADVANCE,
    )
    db.commit()
    accept_booking(db, booking.id, override_advance=True, actor=actor)

    accepted = db.execute(
        select(func.count())
        .select_from(BookingEvent)
        .where(
            BookingEvent.booking_id == booking.id,
            BookingEvent.event_type == "accepted",
        )
    ).scalar_one()
    assert accepted == 1
