"""Property test for the time sheet.

Feature: cinematic-celebration-system, Property 12: Time sheet returns only
accepted bookings, ordered by slot (``slot.sort_order`` ascending).
"""

from __future__ import annotations

import secrets

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import CurrentUser
from app.models.booking import Booking
from app.services import sheets as sheets_service
from tests.factories import future_date, make_location, make_plan, make_slot

pytestmark = pytest.mark.integration

_STATUSES = ("pending", "accepted", "rejected", "expired")


def _admin_actor() -> CurrentUser:
    """An admin principal (location access is unrestricted)."""
    return CurrentUser(id=1, username="admin", role="admin", location_id=None)


def _clear_bookings(db: Session) -> None:
    for booking in db.execute(select(Booking)).scalars().all():
        db.delete(booking)
    db.flush()


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(statuses=st.lists(st.sampled_from(_STATUSES), min_size=1, max_size=8))
def test_timesheet_accepted_only_ordered_by_slot(
    db: Session, statuses: list[str]
) -> None:
    """Property 12: timesheet rows are accepted-only and slot-ordered.

    A distinct slot is created per booking (random ``sort_order``) so the
    active-slot unique index is never violated regardless of status mix.
    """
    _clear_bookings(db)
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    on_date = future_date()

    accepted_slot_ids: set[int] = set()
    for index, status in enumerate(statuses):
        sort_order = secrets.randbelow(1000)
        slot = make_slot(db, plan.id, sort_order=sort_order)
        booking = Booking(
            booking_reference=f"CC-{secrets.token_hex(4)}",
            public_token=secrets.token_urlsafe(12),
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=on_date,
            booking_name=f"Customer {index}",
            email="t@example.com",
            people=4,
            plan_price_paise=400000,
            subtotal_paise=400000,
            total_paise=400000,
            advance_paise=50000,
            status=status,
        )
        db.add(booking)
        db.flush()
        if status == "accepted":
            accepted_slot_ids.add(slot.id)

    rows = sheets_service.timesheet(
        db, _admin_actor(), location_id=loc.id, on_date=on_date
    )

    # Only accepted bookings appear; no non-accepted slot leaks in.
    returned_slot_ids = {row.slot_id for row in rows}
    assert returned_slot_ids == accepted_slot_ids
    assert len(rows) == statuses.count("accepted")

    # Rows are ordered by slot.sort_order ascending.
    sort_orders = [row.slot_sort_order for row in rows]
    assert sort_orders == sorted(sort_orders)
