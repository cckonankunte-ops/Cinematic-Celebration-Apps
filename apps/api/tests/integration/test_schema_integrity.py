"""Schema integrity tests (real PostgreSQL).

Verifies the DB-level guarantees from the design:
- uq_bookings_active_slot allows only one active (pending|accepted) booking per
  (location, slot, date), but permits a rejected/expired booking to coexist.
- CHECK constraints reject bad payments, booking_items, and booking_events rows.
"""

from __future__ import annotations

import secrets
from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.cake import Cake
from app.models.location import Location
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.slot import Slot

pytestmark = pytest.mark.integration


def _seed_location_plan_slot(db: Session) -> tuple[int, int, int]:
    loc = Location(name="Hulimavu", slug=f"hul-{secrets.token_hex(3)}")
    db.add(loc)
    db.flush()
    plan = Plan(
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
    db.add(plan)
    db.flush()
    slot = Slot(
        plan_id=plan.id,
        description="9 AM - 12 PM",
        effective_from=date(2020, 1, 1),
        effective_to=date(2099, 12, 31),
        sort_order=1,
    )
    db.add(slot)
    db.flush()
    return loc.id, plan.id, slot.id


def _seed_location_two_plans_one_slot(db: Session) -> tuple[int, int, int, int]:
    """Seed one location, two plans (A and B), and one slot owned by plan A.

    Returns ``(location_id, plan_a_id, plan_b_id, slot_id)``. The single slot is
    shared across both plans so the different-plan case can be exercised on the
    4-column key ``(location_id, plan_id, slot_id, booking_date)``.
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


def _make_booking(location_id: int, plan_id: int, slot_id: int, status: str) -> Booking:
    ref = f"CC-{secrets.token_hex(3)}"
    return Booking(
        booking_reference=ref,
        public_token=secrets.token_urlsafe(12),
        location_id=location_id,
        plan_id=plan_id,
        slot_id=slot_id,
        booking_date=date.today() + timedelta(days=10),
        booking_name="Test",
        email="t@example.com",
        people=4,
        plan_price_paise=400000,
        subtotal_paise=400000,
        total_paise=400000,
        advance_paise=50000,
        status=status,
    )


def test_active_slot_unique_index_blocks_second_active_booking(db: Session) -> None:
    # Preservation (Req 3.1): both inserts share a SINGLE plan via
    # _seed_location_plan_slot, so they key on the IDENTICAL
    # (location, plan, slot, date). Under the fixed 4-column index this is still a
    # genuine same-plan duplicate and must raise a unique violation.
    loc, plan, slot = _seed_location_plan_slot(db)
    db.add(_make_booking(loc, plan, slot, "pending"))
    db.commit()

    db.add(_make_booking(loc, plan, slot, "accepted"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_different_plan_same_slot_both_commit(db: Session) -> None:
    """Property 1: different plans may share a slot/date under the 4-column key.

    Two active bookings with the SAME (location, slot, date) but DIFFERENT
    plan_id must BOTH commit with no IntegrityError — the fixed index keys on
    (location_id, plan_id, slot_id, booking_date).
    """
    loc, plan_a, plan_b, slot = _seed_location_two_plans_one_slot(db)
    booking_a = _make_booking(loc, plan_a, slot, "pending")
    db.add(booking_a)
    db.commit()

    booking_b = _make_booking(loc, plan_b, slot, "accepted")
    db.add(booking_b)
    db.commit()

    active = db.execute(
        text(
            "SELECT id FROM bookings "
            "WHERE location_id = :loc AND slot_id = :slot "
            "AND status IN ('pending', 'accepted')"
        ),
        {"loc": loc, "slot": slot},
    ).fetchall()
    assert len(active) == 2
    assert {row[0] for row in active} == {booking_a.id, booking_b.id}


def test_rejected_booking_does_not_hold_slot(db: Session) -> None:
    # Preservation (Req 3.3): same single plan on both rows; the partial predicate
    # WHERE status IN ('pending', 'accepted') still governs under the 4-column key,
    # so a rejected row does not hold the (location, plan, slot, date).
    loc, plan, slot = _seed_location_plan_slot(db)
    db.add(_make_booking(loc, plan, slot, "rejected"))
    db.commit()

    # A new active booking for the same slot/date is allowed alongside a rejected one.
    db.add(_make_booking(loc, plan, slot, "pending"))
    db.commit()


def test_partial_index_predicate_is_present(db: Session) -> None:
    row = db.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'uq_bookings_active_slot'"
        )
    ).first()
    assert row is not None
    indexdef = row[0]
    # Partial predicate preserved (Req 3.5): the index still covers only active
    # (pending|accepted) bookings.
    assert "pending" in indexdef and "accepted" in indexdef
    # Fixed 4-column key is live (Req 3.5): the index now references plan_id and all
    # four key columns in (location_id, plan_id, slot_id, booking_date).
    assert "plan_id" in indexdef
    for column in ("location_id", "plan_id", "slot_id", "booking_date"):
        assert column in indexdef, f"{column} missing from indexdef: {indexdef}"


def test_payment_amount_must_be_positive(db: Session) -> None:
    loc, plan, slot = _seed_location_plan_slot(db)
    booking = _make_booking(loc, plan, slot, "accepted")
    db.add(booking)
    db.commit()

    db.add(Payment(booking_id=booking.id, method="cash", amount_paise=0))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_payment_method_check(db: Session) -> None:
    loc, plan, slot = _seed_location_plan_slot(db)
    booking = _make_booking(loc, plan, slot, "accepted")
    db.add(booking)
    db.commit()

    db.add(Payment(booking_id=booking.id, method="bitcoin", amount_paise=100))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_cake_requires_object_key(db: Session) -> None:
    loc, _, _ = _seed_location_plan_slot(db)
    # object_key is NOT NULL; omitting it must fail at flush/commit.
    db.add(
        Cake(
            location_id=loc,
            description="Chocolate",
            price_paise=50000,
            object_key=None,  # type: ignore[arg-type]
            effective_from=date(2020, 1, 1),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
