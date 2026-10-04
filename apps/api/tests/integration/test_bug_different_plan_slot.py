"""Fix-checking POSITIVE test (real PostgreSQL).

Bugfix: booking-uniqueness-per-plan, Property 1: Expected Behavior -
Different-Plan Bookings Share a Slot.

A *slot* is a shared time window and a *plan* is a separate physical themed
room, so two different plans at the same location, slot, and date are
legitimate, independent bookings. The partial unique index
``uq_bookings_active_slot`` is now keyed on the 4-column key
``(location_id, plan_id, slot_id, booking_date)`` (the fixed schema). As a
result the database correctly ALLOWS a legitimate different-plan booking that
shares a slot/date with another plan.

This file is a FIX-CHECKING test: it runs against the schema reflected by
``Base.metadata.create_all`` in ``conftest.py``, which now builds the FIXED
4-column index. The test PASSES by asserting that the second different-plan
insert COMMITS SUCCESSFULLY with NO unique violation, which confirms the bug is
fixed (Property 1).

Counterexample history (now resolved): under the OLD 3-column key
``(location_id, slot_id, booking_date)`` the second insert wrongly raised::

    (location_id=L, plan_id=A vs B, slot_id=S, booking_date=D)
    -> psycopg errors.UniqueViolation:
       duplicate key value violates unique constraint "uq_bookings_active_slot"

Under the fixed 4-column key the same input is accepted and both rows coexist.

Validates: Requirements 2.1, 2.2 (expected behavior under the fixed schema).
"""

from __future__ import annotations

import secrets
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.location import Location
from app.models.plan import Plan
from app.models.slot import Slot

pytestmark = pytest.mark.integration


def _seed_location_two_plans_one_slot(db: Session) -> tuple[int, int, int, int]:
    """Seed one location, two plans (A and B) on it, and one slot owned by plan A.

    Returns ``(location_id, plan_a_id, plan_b_id, slot_id)``. The single
    ``slot_id`` is reused across both bookings to exercise the different-plan
    case the 4-column index must allow on ``(location_id, slot_id, booking_date)``
    while differing on ``plan_id``.
    """
    loc = Location(name="Hulimavu", slug=f"hul-{secrets.token_hex(3)}")
    db.add(loc)
    db.flush()

    plan_a = Plan(
        location_id=loc.id,
        title="Starlight",
        plan_type=1,
        price_paise=400000,
        people_allowed=4,
        max_people_allowed=10,
        advance_paise=50000,
        effective_from=date(2020, 1, 1),
        effective_to=date(2099, 12, 31),
    )
    plan_b = Plan(
        location_id=loc.id,
        title="Moonlight",
        plan_type=1,
        price_paise=450000,
        people_allowed=4,
        max_people_allowed=10,
        advance_paise=50000,
        effective_from=date(2020, 1, 1),
        effective_to=date(2099, 12, 31),
    )
    db.add_all([plan_a, plan_b])
    db.flush()

    # One slot (belonging to plan A) whose id is shared across both bookings.
    slot = Slot(
        plan_id=plan_a.id,
        description="9 AM - 12 PM",
        effective_from=date(2020, 1, 1),
        effective_to=date(2099, 12, 31),
        sort_order=1,
    )
    db.add(slot)
    db.flush()

    return loc.id, plan_a.id, plan_b.id, slot.id


def _make_booking(
    location_id: int, plan_id: int, slot_id: int, booking_date: date, status: str
) -> Booking:
    ref = f"CC-{secrets.token_hex(3)}"
    return Booking(
        booking_reference=ref,
        public_token=secrets.token_urlsafe(12),
        location_id=location_id,
        plan_id=plan_id,
        slot_id=slot_id,
        booking_date=booking_date,
        booking_name="Test",
        email="t@example.com",
        people=4,
        plan_price_paise=400000,
        subtotal_paise=400000,
        total_paise=400000,
        advance_paise=50000,
        status=status,
    )


def test_different_plan_same_slot_allowed_on_fixed_schema(db: Session) -> None:
    """FIX-CHECKING: different-plan booking is allowed under the fixed 4-column index.

    Seeds one location, two plans, and one shared slot. An active (pending)
    booking for plan A holds ``(location, slot, date)``. A second active
    (accepted) booking for plan B at the SAME ``(location, slot, date)`` but a
    DIFFERENT ``plan_id`` is a different physical room and MUST be allowed under
    the fixed 4-column key ``(location_id, plan_id, slot_id, booking_date)``.

    SUCCESS CASE (Property 1): the second commit succeeds with NO
    ``IntegrityError`` and both active rows coexist.

    Counterexample history (now resolved): under the OLD 3-column key the same
    input raised ``duplicate key value violates unique constraint
    "uq_bookings_active_slot"``.
    """
    loc, plan_a, plan_b, slot = _seed_location_two_plans_one_slot(db)
    booking_date = date.today() + timedelta(days=10)

    # First active booking for plan A — commits cleanly and holds the slot.
    booking_a = _make_booking(loc, plan_a, slot, booking_date, "pending")
    db.add(booking_a)
    db.commit()

    # Second active booking: SAME (location, slot, date), DIFFERENT plan (B).
    # This is a legitimate different-room booking that the fixed 4-column index
    # now allows. It must commit with no unique violation.
    booking_b = _make_booking(loc, plan_b, slot, booking_date, "accepted")
    db.add(booking_b)
    db.commit()

    # Both active rows coexist for the shared (location, slot, date).
    active_count = db.execute(
        select(Booking)
        .where(
            Booking.location_id == loc,
            Booking.slot_id == slot,
            Booking.booking_date == booking_date,
            Booking.status.in_(("pending", "accepted")),
        )
    ).scalars().all()
    assert len(active_count) == 2
    assert {b.id for b in active_count} == {booking_a.id, booking_b.id}
    assert {b.plan_id for b in active_count} == {plan_a, plan_b}


def test_create_customer_booking_different_plan_not_reproducible_via_service() -> None:
    """SECONDARY (service-level): skipped — not observable via the service.

    The service's ``validate_booking_request`` -> ``_load_valid_slot`` requires
    the slot belong to the booking's ``plan_id``. A different-plan booking must
    therefore use a DIFFERENT slot, so two different plans never share one
    ``slot_id`` through the service path. The different-plan case is only
    observable at the DB index level, which the primary DB-level test
    (``test_different_plan_same_slot_allowed_on_fixed_schema``) authoritatively
    covers. This slot-ownership enforcement is unchanged by the fix.
    """
    pytest.skip(
        "Different-plan behavior is only observable at the DB index level: the "
        "service enforces slot-ownership (slot.plan_id == booking.plan_id), so a "
        "different-plan booking cannot reuse the same slot_id via "
        "create_customer_booking. The primary DB-level test covers this case."
    )
