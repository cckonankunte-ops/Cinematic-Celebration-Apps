"""Integration tests for customer-booking-flow-v2 Task 3 (real PostgreSQL).

Covers kids guest-cap, disallowed-time enforcement (open-mode availability +
customer booking rejection; config is forward-looking), and advance resolution
(identical in preview/create; recomputed against the FINAL total incl. coupon).

Test cases: K5 (cap), T1 (disallowed availability + reject), T3 (config
forward-only), adults=0, A2 (preview == create advance), A4 (coupon lowers the
matched advance band).
"""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.models.advance_rule import AdvanceRule
from app.models.location_disallowed_time import LocationDisallowedTime
from app.models.plan_pricing import PlanPricing
from app.schemas.booking import BookingCreate, PublicPreviewRequest
from app.services import booking as booking_service
from app.services import catalog as catalog_service
from app.services.slots import ActorKind
from tests.factories import (
    FAR_FUTURE,
    FAR_PAST,
    future_date,
    make_coupon,
    make_location,
    make_plan,
    make_slot,
)

pytestmark = pytest.mark.integration


def _advance_rule(
    db: Session, location_id: int, *, min_total: int, advance: int
) -> AdvanceRule:
    rule = AdvanceRule(
        location_id=location_id, min_total_paise=min_total, advance_paise=advance
    )
    db.add(rule)
    db.flush()
    return rule


def _price_duration(
    db: Session, plan_id: int, duration: int, price_paise: int = 120000
) -> None:
    """Open-mode bookings price by duration via plan_pricing; seed a row."""
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
    db.flush()


def _disallowed(
    db: Session,
    location_id: int,
    *,
    start: time,
    end: time,
    max_duration_minutes: int | None = None,
) -> LocationDisallowedTime:
    row = LocationDisallowedTime(
        location_id=location_id,
        start_time=start,
        end_time=end,
        max_duration_minutes=max_duration_minutes,
    )
    db.add(row)
    db.flush()
    return row


# --- K5: total guests (adults + kids) over max is rejected --------------------
def test_k5_total_guests_over_max_rejected(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id, people_allowed=2, max_people_allowed=6)
    db.flush()
    # 4 adults + 3 kids = 7 > max 6 -> rejected for a customer (no bypass).
    with pytest.raises(ValidationFailedError):
        booking_service.validate_booking_request(
            db,
            location_id=loc.id,
            plan_id=plan.id,
            booking_date=future_date(),
            people=4,
            kids=3,
            cake_id=None,
            special_decor=[],
            combos=[],
        )


def test_k5_total_within_max_accepted(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id, people_allowed=2, max_people_allowed=6)
    db.flush()
    req = booking_service.validate_booking_request(
        db,
        location_id=loc.id,
        plan_id=plan.id,
        booking_date=future_date(),
        people=4,
        kids=2,  # 6 == max
        cake_id=None,
        special_decor=[],
        combos=[],
    )
    assert req.people == 4
    assert req.kids == 2


def test_adults_zero_rejected(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id, people_allowed=2, max_people_allowed=10)
    db.flush()
    with pytest.raises(ValidationFailedError):
        booking_service.validate_booking_request(
            db,
            location_id=loc.id,
            plan_id=plan.id,
            booking_date=future_date(),
            people=0,
            kids=3,
            cake_id=None,
            special_decor=[],
            combos=[],
        )


# --- T1: a disallowed range hides open-mode starts + rejects a customer -------
def test_t1_disallowed_hides_start_and_rejects_customer(db: Session) -> None:
    # Open-mode branch open 10:00-22:00; disallow 20:00-21:00.
    loc = make_location(db, name="Open")
    loc.booking_mode = "open"
    loc.opens_at = time(10, 0)
    loc.closes_at = time(22, 0)
    plan = make_plan(db, loc.id)
    _price_duration(db, plan.id, 60)
    _disallowed(db, loc.id, start=time(20, 0), end=time(21, 0))
    db.flush()

    avail = catalog_service.generate_open_availability(
        db,
        plan.id,
        loc.id,
        future_date(),
        60,
        actor=ActorKind.PUBLIC,
        now=None,
    )
    by_start = {a.start_time: a.is_available for a in avail}
    # A 20:00 start overlaps the disallowed range -> unavailable.
    assert by_start.get(time(20, 0)) is False
    # An outside-range start (e.g. 14:00) stays available.
    assert by_start.get(time(14, 0)) is True

    # A customer booking for the disallowed window is rejected.
    with pytest.raises(ValidationFailedError):
        booking_service.create_customer_booking(
            db,
            BookingCreate(
                location_id=loc.id,
                plan_id=plan.id,
                start_time=time(20, 0),
                duration_minutes=60,
                booking_date=future_date(),
                booking_name="Cust",
                phone="9876543210",
                people=2,
            ),
        )


# --- T3: changing disallowed ranges does not alter existing bookings ----------
def test_t3_config_is_forward_only(db: Session) -> None:
    loc = make_location(db, name="Open2")
    loc.booking_mode = "open"
    loc.opens_at = time(10, 0)
    loc.closes_at = time(22, 0)
    plan = make_plan(db, loc.id)
    _price_duration(db, plan.id, 60)
    db.flush()

    # Book 14:00 BEFORE any disallowed range exists -> succeeds.
    result = booking_service.create_customer_booking(
        db,
        BookingCreate(
            location_id=loc.id,
            plan_id=plan.id,
            start_time=time(14, 0),
            duration_minutes=60,
            booking_date=future_date(),
            booking_name="Cust",
            phone="9876543210",
            people=2,
        ),
    )
    booking = booking_service.get_booking_by_token(db, result.booking_token)
    assert booking.status == "pending"

    # Now add a disallowed range covering 14:00. The existing booking is NOT
    # altered (config is forward-looking only).
    _disallowed(db, loc.id, start=time(13, 30), end=time(15, 0))
    db.flush()
    db.refresh(booking)
    assert booking.status == "pending"
    assert booking.start_time == time(14, 0)


# --- A2: resolved advance is identical in preview and create ------------------
def test_a2_advance_identical_preview_and_create(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id, price_paise=120000, advance_paise=50000)
    slot = make_slot(db, plan.id)
    _advance_rule(db, loc.id, min_total=100000, advance=70000)
    db.flush()

    when = future_date()
    shared = dict(
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        booking_date=when,
        people=1,
    )
    preview = booking_service.preview_booking(
        db, PublicPreviewRequest(**shared), is_customer=True
    )
    result = booking_service.create_customer_booking(
        db,
        BookingCreate(booking_name="Cust", phone="9876543210", **shared),
    )
    booking = booking_service.get_booking_by_token(db, result.booking_token)

    # total 120000 meets the 100000 rule -> advance 70000 in BOTH paths.
    assert preview.advance_paise == 70000
    assert result.advance_paise == 70000
    assert booking.advance_paise == 70000


# --- A4: advance resolves against the FINAL total (coupon lowers the band) -----
def test_a4_coupon_lowers_matched_advance_band(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id, price_paise=210000, advance_paise=50000)
    slot = make_slot(db, plan.id)
    # Bands: >=200000 -> 75000; >=100000 -> 50000.
    _advance_rule(db, loc.id, min_total=200000, advance=75000)
    _advance_rule(db, loc.id, min_total=100000, advance=50000)
    # A flat ₹200 coupon drops 210000 -> 190000, crossing below the 200k band.
    make_coupon(db, loc.id, code="DROP", type="flat", value=20000)
    db.flush()

    when = future_date()
    # Without coupon: total 210000 -> 75000 band.
    no_coupon = booking_service.preview_booking(
        db,
        PublicPreviewRequest(
            location_id=loc.id, plan_id=plan.id, slot_id=slot.id,
            booking_date=when, people=1,
        ),
        is_customer=True,
    )
    assert no_coupon.total_paise == 210000
    assert no_coupon.advance_paise == 75000

    # With coupon: total 190000 -> falls to the 50000 band.
    with_coupon = booking_service.preview_booking(
        db,
        PublicPreviewRequest(
            location_id=loc.id, plan_id=plan.id, slot_id=slot.id,
            booking_date=when, people=1, coupon_code="DROP",
        ),
        is_customer=True,
    )
    assert with_coupon.total_paise == 190000
    assert with_coupon.advance_paise == 50000
