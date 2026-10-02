"""Property test for booking reference / public token uniqueness.

Feature: cinematic-celebration-system, Property 6: Booking references and public
tokens are globally unique.

Validates: Requirements 5.6

create_customer_booking calls get_payment_provider().create_order, which in
Phase 1 is the ManualProvider (pure, no network), so it is safe to call directly.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.schemas.booking import BookingCreate
from app.services.booking import create_customer_booking
from tests.factories import make_location, make_plan, make_slot

pytestmark = pytest.mark.integration


def _make_bookable(db: Session) -> tuple[int, int, int]:
    """Seed one location + plan + slot and return their ids."""
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot = make_slot(db, plan.id)
    db.flush()
    return loc.id, plan.id, slot.id


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(count=st.integers(min_value=2, max_value=8))
def test_references_and_tokens_are_unique(db: Session, count: int) -> None:
    """Many bookings across dates yield distinct references and tokens."""
    location_id, plan_id, slot_id = _make_bookable(db)

    tokens: list[str] = []
    base = date.today() + timedelta(days=5)
    for i in range(count):
        # Distinct dates keep each booking on a unique active (location, slot, date).
        result = create_customer_booking(
            db,
            BookingCreate(
                location_id=location_id,
                plan_id=plan_id,
                slot_id=slot_id,
                booking_date=base + timedelta(days=i),
                booking_name=f"Customer {i}",
                email=f"c{i}@example.com",
                people=4,
            ),
        )
        tokens.append(result.booking_token)

    references = db.execute(select(Booking.booking_reference)).scalars().all()
    all_tokens = db.execute(select(Booking.public_token)).scalars().all()

    assert len(tokens) == count
    assert len(set(tokens)) == count
    assert len(set(references)) == len(references)
    assert len(set(all_tokens)) == len(all_tokens)
