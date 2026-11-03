"""Schema contract for per-branch booking mode (model/create_all level).

The integration harness builds the schema from the SQLAlchemy models via
create_all (not Alembic), so this verifies the model-level outcome of migration
0013:
- locations default to booking_mode='slot';
- the CHECK constraint rejects an invalid booking_mode;
- bookings.slot_id accepts NULL (open-mode bookings carry no slot row).

The Alembic migration itself (additive column + nullable alter) is exercised
separately when migrations are run against the Codespace Postgres.
"""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.location import Location
from tests.factories import future_date, make_location, make_plan

pytestmark = pytest.mark.integration


def test_location_defaults_to_slot_mode(db: Session) -> None:
    loc = make_location(db)
    db.commit()
    db.refresh(loc)
    assert loc.booking_mode == "slot"


def test_location_booking_mode_check_rejects_invalid(db: Session) -> None:
    loc = Location(name="Bad", slug="bad-mode", booking_mode="nonsense")
    db.add(loc)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_location_accepts_open_mode(db: Session) -> None:
    loc = make_location(db)
    loc.booking_mode = "open"
    db.commit()
    db.refresh(loc)
    assert loc.booking_mode == "open"


def test_booking_slot_id_accepts_null(db: Session) -> None:
    """An open-mode booking persists with slot_id = NULL."""
    loc = make_location(db)
    loc.booking_mode = "open"
    plan = make_plan(db, loc.id)
    db.commit()

    booking = Booking(
        booking_reference="CC-OPEN-20261104-0001",
        public_token="open-token-0001",
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=None,  # open mode: no slot row
        booking_date=future_date(),
        start_time=time(15, 0),
        duration_minutes=120,
        booking_name="Open Mode",
        people=2,
        plan_price_paise=plan.price_paise,
        extra_guest_paise=0,
        subtotal_paise=plan.price_paise,
        total_paise=plan.price_paise,
        status="pending",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    assert booking.slot_id is None
