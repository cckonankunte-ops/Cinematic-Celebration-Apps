"""Admin-only extra time on open-mode bookings (real PostgreSQL).

Extra time lengthens the held window past the priced duration and adds a flat
price to the total. It is admin-only and open-mode-only, never on the public
booking request, and must not overlap the next booking (cleaning buffer incl.).

The DB exclusion constraint is migration-only (the harness uses create_all), so
overlap here is verified through the service pre-check, as in the other
open-mode tests.
"""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, SlotUnavailableError, ValidationFailedError
from app.core.security import CurrentUser
from app.models.booking_event import BookingEvent
from app.models.plan_pricing import PlanPricing
from app.schemas.booking import (
    AdminBookingCreate,
    BookingCreate,
    BookingUpdate,
    DecorSelectionIn,
)
from app.services import booking as booking_service
from app.services import catalog as catalog_service
from app.services import sheets as sheets_service
from tests.factories import (
    FAR_FUTURE,
    FAR_PAST,
    future_date,
    make_decor,
    make_location,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration

BASE_2H = 120_000  # Rs 1,200 for the 120-minute price row
EXTRA_PRICE = 50_000  # Rs 500 flat for the extra time


def _admin(db: Session) -> CurrentUser:
    user = make_user(db, "admin", location_id=None)
    return CurrentUser(id=user.id, username=user.username, role="admin", location_id=None)


def _staff(db: Session, location_id: int) -> CurrentUser:
    user = make_user(db, "staff", location_id=location_id)
    return CurrentUser(
        id=user.id, username=user.username, role="staff", location_id=location_id
    )


def _price(db: Session, plan_id: int, duration: int, price_paise: int) -> None:
    db.add(
        PlanPricing(
            plan_id=plan_id,
            duration_minutes=duration,
            price_paise=price_paise,
            advance_paise=0,
            effective_from=FAR_PAST,
            effective_to=FAR_FUTURE,
            is_active=True,
        )
    )


def _setup(db: Session):
    """An open-mode branch with a plan priced for 60 and 120 minutes."""
    loc = make_location(db)
    loc.booking_mode = "open"
    plan = make_plan(db, loc.id)
    _price(db, plan.id, 60, 70_000)
    _price(db, plan.id, 120, BASE_2H)
    db.commit()
    return loc, plan


def _create(loc_id: int, plan_id: int, start: time, duration: int, when, **extra):
    return AdminBookingCreate(
        location_id=loc_id,
        plan_id=plan_id,
        start_time=start,
        duration_minutes=duration,
        booking_date=when,
        booking_name="Meera",
        phone="9876543210",
        people=2,
        special_decor=extra.pop("special_decor", []),
        combos=[],
        **extra,
    )


def test_extra_time_adds_flat_price_and_extends_the_window(db: Session) -> None:
    admin = _admin(db)
    loc, plan = _setup(db)
    when = future_date()

    booking = booking_service.create_admin_booking(
        db,
        _create(
            loc.id, plan.id, time(11, 0), 120, when,
            extra_minutes=60, extra_time_price_paise=EXTRA_PRICE,
        ),
        admin,
    )

    assert booking.duration_minutes == 120
    assert booking.extra_minutes == 60
    assert booking.extra_time_price_paise == EXTRA_PRICE
    assert booking.total_paise == BASE_2H + EXTRA_PRICE

    # The held window is 11:00-14:00 (+30 min buffer): 14:00 clashes, 14:30 is free.
    with pytest.raises(SlotUnavailableError):
        booking_service.create_admin_booking(
            db, _create(loc.id, plan.id, time(14, 0), 60, when), admin
        )
    ok = booking_service.create_admin_booking(
        db, _create(loc.id, plan.id, time(14, 30), 60, when), admin
    )
    assert ok.extra_minutes == 0 and ok.extra_time_price_paise == 0


def test_extra_time_refused_when_it_runs_into_the_next_booking(db: Session) -> None:
    admin = _admin(db)
    loc, plan = _setup(db)
    when = future_date()
    booking_service.create_admin_booking(
        db, _create(loc.id, plan.id, time(15, 0), 60, when), admin
    )

    # 11:00 + 2h ends 13:00; the next booking starts 15:00; 30 min buffer => 90 min.
    assert catalog_service.max_extra_minutes(
        db, plan.id, loc.id, when, time(11, 0), 120
    ) == 90

    with pytest.raises(SlotUnavailableError):
        booking_service.create_admin_booking(
            db,
            _create(
                loc.id, plan.id, time(11, 0), 120, when,
                extra_minutes=91, extra_time_price_paise=EXTRA_PRICE,
            ),
            admin,
        )
    fits = booking_service.create_admin_booking(
        db,
        _create(
            loc.id, plan.id, time(11, 0), 120, when,
            extra_minutes=90, extra_time_price_paise=EXTRA_PRICE,
        ),
        admin,
    )
    assert fits.extra_minutes == 90


def test_max_extra_minutes_is_unlimited_without_a_later_booking(db: Session) -> None:
    loc, plan = _setup(db)
    assert (
        catalog_service.max_extra_minutes(
            db, plan.id, loc.id, future_date(), time(11, 0), 120
        )
        is None
    )


def test_staff_cannot_add_or_change_extra_time(db: Session) -> None:
    admin = _admin(db)
    loc, plan = _setup(db)
    staff = _staff(db, loc.id)
    when = future_date()

    with pytest.raises(ForbiddenError):
        booking_service.create_admin_booking(
            db,
            _create(
                loc.id, plan.id, time(11, 0), 120, when,
                extra_minutes=30, extra_time_price_paise=EXTRA_PRICE,
            ),
            staff,
        )
    db.rollback()

    booking = booking_service.create_admin_booking(
        db, _create(loc.id, plan.id, time(11, 0), 120, when), admin
    )
    with pytest.raises(ForbiddenError):
        booking_service.update_booking(
            db,
            booking.id,
            BookingUpdate(extra_minutes=30, extra_time_price_paise=EXTRA_PRICE),
            staff,
        )


def test_extra_time_needs_an_open_branch_and_minutes(db: Session) -> None:
    admin = _admin(db)
    loc, plan = _setup(db)
    when = future_date()

    # A price with no minutes would charge for time that is not held.
    with pytest.raises(ValidationFailedError, match="needs extra minutes"):
        booking_service.create_admin_booking(
            db,
            _create(
                loc.id, plan.id, time(11, 0), 120, when,
                extra_time_price_paise=EXTRA_PRICE,
            ),
            admin,
        )
    db.rollback()

    # Slot-mode branches do not support extra time.
    slot_loc = make_location(db, name="SlotBranch")
    slot_plan = make_plan(db, slot_loc.id)
    slot = make_slot(
        db, slot_plan.id, description="11 AM - 1 PM",
        start_time=time(11, 0), duration_minutes=120,
    )
    db.commit()
    with pytest.raises(ValidationFailedError, match="open-booking"):
        booking_service.create_admin_booking(
            db,
            AdminBookingCreate(
                location_id=slot_loc.id,
                plan_id=slot_plan.id,
                slot_id=slot.id,
                booking_date=when,
                booking_name="Meera",
                phone="9876543210",
                people=2,
                special_decor=[],
                combos=[],
                extra_minutes=30,
                extra_time_price_paise=EXTRA_PRICE,
            ),
            admin,
        )


def test_edit_adds_and_clears_extra_time_with_an_audit_event(db: Session) -> None:
    admin = _admin(db)
    loc, plan = _setup(db)
    booking = booking_service.create_admin_booking(
        db, _create(loc.id, plan.id, time(11, 0), 120, future_date()), admin
    )
    assert booking.total_paise == BASE_2H

    updated = booking_service.update_booking(
        db,
        booking.id,
        BookingUpdate(extra_minutes=45, extra_time_price_paise=EXTRA_PRICE),
        admin,
    )
    assert updated.extra_minutes == 45
    assert updated.total_paise == BASE_2H + EXTRA_PRICE

    event = db.execute(
        select(BookingEvent)
        .where(BookingEvent.booking_id == booking.id, BookingEvent.event_type == "edited")
        .order_by(BookingEvent.id.desc())
    ).scalars().first()
    assert event is not None
    assert event.old_value["extra_minutes"] == 0
    assert event.new_value["extra_minutes"] == 45
    assert event.new_value["extra_time_price_paise"] == EXTRA_PRICE

    cleared = booking_service.update_booking(
        db,
        booking.id,
        BookingUpdate(extra_minutes=0, extra_time_price_paise=0),
        admin,
    )
    assert cleared.extra_minutes == 0
    assert cleared.total_paise == BASE_2H


def test_an_unrelated_edit_keeps_the_extra_time_price(db: Session) -> None:
    admin = _admin(db)
    loc, plan = _setup(db)
    booking = booking_service.create_admin_booking(
        db,
        _create(
            loc.id, plan.id, time(11, 0), 120, future_date(),
            extra_minutes=60, extra_time_price_paise=EXTRA_PRICE,
        ),
        admin,
    )
    updated = booking_service.update_booking(db, booking.id, BookingUpdate(people=3), admin)
    assert updated.extra_minutes == 60
    assert updated.extra_time_price_paise == EXTRA_PRICE
    assert updated.total_paise >= BASE_2H + EXTRA_PRICE


def test_edit_extra_time_refused_when_the_next_booking_is_too_close(db: Session) -> None:
    admin = _admin(db)
    loc, plan = _setup(db)
    when = future_date()
    booking_service.create_admin_booking(
        db, _create(loc.id, plan.id, time(15, 0), 60, when), admin
    )
    booking = booking_service.create_admin_booking(
        db, _create(loc.id, plan.id, time(11, 0), 120, when), admin
    )
    with pytest.raises(SlotUnavailableError):
        booking_service.update_booking(
            db,
            booking.id,
            BookingUpdate(extra_minutes=120, extra_time_price_paise=EXTRA_PRICE),
            admin,
        )
    db.rollback()
    db.refresh(booking)
    assert booking.extra_minutes == 0


def test_public_booking_request_has_no_extra_time_fields() -> None:
    assert "extra_minutes" not in BookingCreate.model_fields
    assert "extra_time_price_paise" not in BookingCreate.model_fields


def test_timesheet_shows_the_extended_end_and_sheet_details(db: Session) -> None:
    admin = _admin(db)
    loc, plan = _setup(db)
    decor = make_decor(db, loc.id)
    db.commit()
    when = future_date()

    booking_service.create_admin_booking(
        db,
        _create(
            loc.id, plan.id, time(11, 0), 120, when,
            extra_minutes=60, extra_time_price_paise=EXTRA_PRICE,
            special_decor=[DecorSelectionIn(id=decor.id, quantity=2)],
            led_name="MEERA",
        ),
        admin,
    )
    rows = sheets_service.timesheet(db, admin, location_id=loc.id, on_date=when)

    assert len(rows) == 1
    # 11:00 + 120 + 60 extra = 2:00 PM.
    assert rows[0].slot_description == "11:00 AM - 2:00 PM"
    # More than one of an item shows its quantity; the LED text is on the row.
    assert rows[0].special_decor == "2 Rose bouquet"
    assert rows[0].led_name == "MEERA"


def test_timesheet_decor_with_quantity_one_shows_only_the_name(db: Session) -> None:
    admin = _admin(db)
    loc, plan = _setup(db)
    decor = make_decor(db, loc.id)
    db.commit()
    when = future_date()
    booking_service.create_admin_booking(
        db,
        _create(
            loc.id, plan.id, time(11, 0), 120, when,
            special_decor=[DecorSelectionIn(id=decor.id, quantity=1)],
        ),
        admin,
    )
    rows = sheets_service.timesheet(db, admin, location_id=loc.id, on_date=when)
    assert rows[0].special_decor == "Rose bouquet"


def test_timesheet_is_ordered_by_start_time(db: Session) -> None:
    admin = _admin(db)
    loc, plan = _setup(db)
    when = future_date()
    # Created out of order on purpose.
    for start in (time(18, 0), time(11, 0), time(14, 30)):
        booking_service.create_admin_booking(
            db, _create(loc.id, plan.id, start, 60, when), admin
        )
    rows = sheets_service.timesheet(db, admin, location_id=loc.id, on_date=when)
    assert [r.slot_description for r in rows] == [
        "11:00 AM - 12:00 PM",
        "2:30 PM - 3:30 PM",
        "6:00 PM - 7:00 PM",
    ]
