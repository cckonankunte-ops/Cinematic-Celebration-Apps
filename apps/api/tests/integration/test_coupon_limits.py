"""Integration test — coupon limit violation is rejected (real PostgreSQL).

Feature: admin-booking-edit, Property 21: Coupon limit violation is rejected.
Usage limits are enforced through the service layer and the per-customer limit
counts distinct Normalized_Phone keys: two formatting variants of the same
number count as ONE customer, while two different real numbers count as two.
A booking's own existing redemption is excluded (self-exclusion on edit).

Validates: Requirements 20.2, 21.3, 21.5
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.errors import CouponNotApplicableError
from app.core.phone import normalize_indian_mobile
from app.models.coupon_redemption import CouponRedemption
from app.services import coupon as coupon_service
from app.services.pricing import ValidatedCoupon
from tests.factories import (
    make_booking,
    make_coupon,
    make_location,
    make_plan,
    make_slot,
)

pytestmark = pytest.mark.integration

_PRE_COUPON_TOTAL = 100000


def _seed_location_plan_slot(db: Session) -> tuple[int, int, int]:
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot = make_slot(db, plan.id)
    db.flush()
    return loc.id, plan.id, slot.id


def _record_redemption(
    db: Session, *, coupon_id: int, booking_id: int, customer_key: str
) -> None:
    db.add(
        CouponRedemption(
            coupon_id=coupon_id,
            booking_id=booking_id,
            customer_key=customer_key,
            discount_paise=10000,
        )
    )
    db.flush()


def test_per_customer_limit_rejects_same_phone(db: Session) -> None:
    """A phone that already redeemed up to its per-customer limit is rejected."""
    loc_id, plan_id, slot_id = _seed_location_plan_slot(db)
    coupon = make_coupon(db, loc_id, code="SAVE10", per_customer_limit=1)
    booking = make_booking(
        db, location_id=loc_id, plan_id=plan_id, slot_id=slot_id, phone="9876543210"
    )
    _record_redemption(
        db, coupon_id=coupon.id, booking_id=booking.id, customer_key="9876543210"
    )

    # A fresh attempt (different/None booking) for the SAME phone is blocked.
    with pytest.raises(CouponNotApplicableError):
        coupon_service.resolve_and_validate(
            db,
            "SAVE10",
            location_id=loc_id,
            pre_coupon_total=_PRE_COUPON_TOTAL,
            customer_key="9876543210",
            booking_id=None,
            on=date.today(),
        )


def test_per_customer_limit_allows_different_phone(db: Session) -> None:
    """A different real number has its own per-customer budget and succeeds."""
    loc_id, plan_id, slot_id = _seed_location_plan_slot(db)
    coupon = make_coupon(db, loc_id, code="SAVE10", per_customer_limit=1)
    booking = make_booking(
        db, location_id=loc_id, plan_id=plan_id, slot_id=slot_id, phone="9876543210"
    )
    _record_redemption(
        db, coupon_id=coupon.id, booking_id=booking.id, customer_key="9876543210"
    )

    result = coupon_service.resolve_and_validate(
        db,
        "SAVE10",
        location_id=loc_id,
        pre_coupon_total=_PRE_COUPON_TOTAL,
        customer_key="9999988888",  # a different real customer
        booking_id=None,
        on=date.today(),
    )
    assert isinstance(result, ValidatedCoupon)
    assert result.code == "SAVE10"


def test_per_customer_limit_is_formatting_invariant(db: Session) -> None:
    """Two formatting variants of one number count as the SAME customer.

    A redemption recorded under '9876543210' blocks a new attempt whose key is
    the normalized form of '+91 98765 43210' because both normalize to the same
    10-digit key (mirroring how the booking service derives customer_key).
    """
    loc_id, plan_id, slot_id = _seed_location_plan_slot(db)
    coupon = make_coupon(db, loc_id, code="SAVE10", per_customer_limit=1)
    booking = make_booking(
        db, location_id=loc_id, plan_id=plan_id, slot_id=slot_id, phone="9876543210"
    )
    _record_redemption(
        db, coupon_id=coupon.id, booking_id=booking.id, customer_key="9876543210"
    )

    variant_key = normalize_indian_mobile("+91 98765 43210")
    assert variant_key == "9876543210"

    with pytest.raises(CouponNotApplicableError):
        coupon_service.resolve_and_validate(
            db,
            "SAVE10",
            location_id=loc_id,
            pre_coupon_total=_PRE_COUPON_TOTAL,
            customer_key=variant_key or "",
            booking_id=None,
            on=date.today(),
        )


def test_total_usage_limit_rejects_any_customer(db: Session) -> None:
    """When the global usage limit is reached, any customer is rejected."""
    loc_id, plan_id, slot_id = _seed_location_plan_slot(db)
    coupon = make_coupon(db, loc_id, code="SAVE10", total_usage_limit=1)
    booking = make_booking(
        db, location_id=loc_id, plan_id=plan_id, slot_id=slot_id, phone="9876543210"
    )
    _record_redemption(
        db, coupon_id=coupon.id, booking_id=booking.id, customer_key="9876543210"
    )

    # Even a brand-new customer cannot use it once the global limit is exhausted.
    with pytest.raises(CouponNotApplicableError):
        coupon_service.resolve_and_validate(
            db,
            "SAVE10",
            location_id=loc_id,
            pre_coupon_total=_PRE_COUPON_TOTAL,
            customer_key="9999988888",
            booking_id=None,
            on=date.today(),
        )


def test_own_redemption_is_excluded_on_edit(db: Session) -> None:
    """Re-validating with the SAME booking id excludes its own redemption.

    Editing a booking that already consumed its only per-customer use must still
    succeed, because the limit check excludes the booking's own prior row.
    """
    loc_id, plan_id, slot_id = _seed_location_plan_slot(db)
    coupon = make_coupon(db, loc_id, code="SAVE10", per_customer_limit=1)
    booking = make_booking(
        db, location_id=loc_id, plan_id=plan_id, slot_id=slot_id, phone="9876543210"
    )
    _record_redemption(
        db, coupon_id=coupon.id, booking_id=booking.id, customer_key="9876543210"
    )

    result = coupon_service.resolve_and_validate(
        db,
        "SAVE10",
        location_id=loc_id,
        pre_coupon_total=_PRE_COUPON_TOTAL,
        customer_key="9876543210",
        booking_id=booking.id,  # exclude this booking's own redemption
        on=date.today(),
    )
    assert isinstance(result, ValidatedCoupon)
    assert result.code == "SAVE10"
