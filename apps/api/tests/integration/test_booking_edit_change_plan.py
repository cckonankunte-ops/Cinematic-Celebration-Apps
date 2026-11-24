"""Changing a booking's plan from the admin edit form (real PostgreSQL).

Regression: ``BookingUpdate`` had no ``plan_id`` and ``update_booking`` always used
the booking's original plan, so picking a slot of the NEW plan failed with "The
selected slot is not valid for this plan or date." and the plan never changed.

Now the plan can be changed (same branch) provided the window is re-picked on the
new plan; the new plan's calendar is checked for overlap, the booking is
re-priced on the new plan, and the audit event records the move.
"""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ItemInvalidError, SlotUnavailableError, ValidationFailedError
from app.core.security import CurrentUser
from app.models.booking import Booking
from app.models.booking_event import BookingEvent
from app.schemas.booking import AdminBookingCreate, BookingUpdate
from app.services import booking as booking_service
from tests.factories import future_date, make_location, make_plan, make_slot, make_user

pytestmark = pytest.mark.integration

WINDOW = {"start_time": time(11, 0), "duration_minutes": 120}


def _admin(db: Session) -> CurrentUser:
    user = make_user(db, "admin", location_id=None)
    return CurrentUser(id=user.id, username=user.username, role="admin", location_id=None)


def _create(loc_id: int, plan_id: int, slot_id: int, when) -> AdminBookingCreate:
    return AdminBookingCreate(
        location_id=loc_id,
        plan_id=plan_id,
        slot_id=slot_id,
        booking_date=when,
        booking_name="Asha",
        phone="9876543210",
        people=4,
        special_decor=[],
        combos=[],
    )


def _two_plans(db: Session):
    """A branch with plan A (Rs 4,000) and plan B (Rs 6,000), one 11 AM slot each."""
    loc = make_location(db)
    plan_a = make_plan(db, loc.id, price_paise=400_000)
    plan_b = make_plan(db, loc.id, price_paise=600_000)
    slot_a = make_slot(db, plan_a.id, description="11 AM - 1 PM", **WINDOW)
    slot_b = make_slot(db, plan_b.id, description="11 AM - 1 PM", **WINDOW)
    db.commit()
    return loc, plan_a, plan_b, slot_a, slot_b


def test_change_plan_moves_booking_and_reprices(db: Session) -> None:
    admin = _admin(db)
    loc, plan_a, plan_b, slot_a, slot_b = _two_plans(db)
    booking = booking_service.create_admin_booking(
        db, _create(loc.id, plan_a.id, slot_a.id, future_date()), admin
    )
    before = booking.total_paise

    updated = booking_service.update_booking(
        db, booking.id, BookingUpdate(plan_id=plan_b.id, slot_id=slot_b.id), admin
    )

    assert (updated.plan_id, updated.slot_id) == (plan_b.id, slot_b.id)
    assert updated.plan_price_paise == 600_000
    assert updated.total_paise == before + 200_000
    assert updated.status == "accepted"

    event = db.execute(
        select(BookingEvent)
        .where(BookingEvent.booking_id == booking.id, BookingEvent.event_type == "edited")
        .order_by(BookingEvent.id.desc())
    ).scalars().first()
    assert event is not None
    assert event.old_value["plan_id"] == plan_a.id
    assert event.new_value["plan_id"] == plan_b.id


def test_change_plan_frees_the_old_plans_slot(db: Session) -> None:
    admin = _admin(db)
    loc, plan_a, plan_b, slot_a, slot_b = _two_plans(db)
    when = future_date()
    booking = booking_service.create_admin_booking(
        db, _create(loc.id, plan_a.id, slot_a.id, when), admin
    )
    booking_service.update_booking(
        db, booking.id, BookingUpdate(plan_id=plan_b.id, slot_id=slot_b.id), admin
    )
    # The same window on plan A can be booked again.
    again = booking_service.create_admin_booking(
        db, _create(loc.id, plan_a.id, slot_a.id, when), admin
    )
    assert again.plan_id == plan_a.id


def test_change_plan_needs_a_slot_on_the_new_plan(db: Session) -> None:
    admin = _admin(db)
    loc, plan_a, plan_b, slot_a, _ = _two_plans(db)
    booking = booking_service.create_admin_booking(
        db, _create(loc.id, plan_a.id, slot_a.id, future_date()), admin
    )
    with pytest.raises(ValidationFailedError, match="plan requires selecting a slot"):
        booking_service.update_booking(db, booking.id, BookingUpdate(plan_id=plan_b.id), admin)
    db.rollback()
    assert db.get(Booking, booking.id).plan_id == plan_a.id


def test_change_plan_rejects_a_slot_of_the_old_plan(db: Session) -> None:
    admin = _admin(db)
    loc, plan_a, plan_b, slot_a, _ = _two_plans(db)
    booking = booking_service.create_admin_booking(
        db, _create(loc.id, plan_a.id, slot_a.id, future_date()), admin
    )
    with pytest.raises(ItemInvalidError):
        booking_service.update_booking(
            db, booking.id, BookingUpdate(plan_id=plan_b.id, slot_id=slot_a.id), admin
        )
    db.rollback()
    assert db.get(Booking, booking.id).plan_id == plan_a.id


def test_change_plan_is_refused_when_the_new_plan_is_busy(db: Session) -> None:
    admin = _admin(db)
    loc, plan_a, plan_b, slot_a, slot_b = _two_plans(db)
    when = future_date()
    booking = booking_service.create_admin_booking(
        db, _create(loc.id, plan_a.id, slot_a.id, when), admin
    )
    # Someone already holds the same window on plan B.
    booking_service.create_admin_booking(db, _create(loc.id, plan_b.id, slot_b.id, when), admin)

    with pytest.raises(SlotUnavailableError):
        booking_service.update_booking(
            db, booking.id, BookingUpdate(plan_id=plan_b.id, slot_id=slot_b.id), admin
        )
    db.rollback()
    kept = db.get(Booking, booking.id)
    assert (kept.plan_id, kept.slot_id) == (plan_a.id, slot_a.id)


def test_change_plan_to_another_branchs_plan_is_refused(db: Session) -> None:
    admin = _admin(db)
    loc, plan_a, _, slot_a, _ = _two_plans(db)
    other = make_location(db, name="Ecity")
    foreign_plan = make_plan(db, other.id)
    foreign_slot = make_slot(db, foreign_plan.id, **WINDOW)
    booking = booking_service.create_admin_booking(
        db, _create(loc.id, plan_a.id, slot_a.id, future_date()), admin
    )
    db.commit()
    with pytest.raises(ItemInvalidError):
        booking_service.update_booking(
            db,
            booking.id,
            BookingUpdate(plan_id=foreign_plan.id, slot_id=foreign_slot.id),
            admin,
        )
    db.rollback()
    assert db.get(Booking, booking.id).plan_id == plan_a.id


def test_sending_the_same_plan_changes_nothing_extra(db: Session) -> None:
    """The edit form always sends plan_id; an unchanged plan is a normal edit."""
    admin = _admin(db)
    loc, plan_a, _, slot_a, _ = _two_plans(db)
    booking = booking_service.create_admin_booking(
        db, _create(loc.id, plan_a.id, slot_a.id, future_date()), admin
    )
    updated = booking_service.update_booking(
        db, booking.id, BookingUpdate(plan_id=plan_a.id, slot_id=slot_a.id, people=5), admin
    )
    assert (updated.plan_id, updated.slot_id, updated.people) == (plan_a.id, slot_a.id, 5)
    event = db.execute(
        select(BookingEvent)
        .where(BookingEvent.booking_id == booking.id, BookingEvent.event_type == "edited")
    ).scalars().first()
    assert event is not None and "plan_id" not in (event.old_value or {})
