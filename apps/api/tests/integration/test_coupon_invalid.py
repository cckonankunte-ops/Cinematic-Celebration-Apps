"""Integration test — invalid coupon is rejected (real PostgreSQL).

Feature: admin-booking-edit, Property 20: Invalid coupon is rejected
(unknown-for-location, wrong location, inactive, or out-of-window codes all
raise CouponInvalidError through the service layer).

Validates: Requirements 21.1, 21.2
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.errors import CouponInvalidError
from app.services import coupon as coupon_service
from tests.factories import make_coupon, make_location

pytestmark = pytest.mark.integration


def test_unknown_code_for_location_is_rejected(db: Session) -> None:
    """A code that does not exist for the location raises CouponInvalidError."""
    loc = make_location(db)
    make_coupon(db, loc.id, code="SAVE10")
    db.flush()

    with pytest.raises(CouponInvalidError):
        coupon_service.resolve_and_validate(
            db,
            "DOESNOTEXIST",
            location_id=loc.id,
            pre_coupon_total=100000,
            customer_key="9876543210",
            booking_id=None,
            on=date.today(),
        )


def test_coupon_from_different_location_is_rejected(db: Session) -> None:
    """A coupon seeded for location B is not valid when resolving for location A."""
    loc_a = make_location(db, name="A")
    loc_b = make_location(db, name="B")
    make_coupon(db, loc_b.id, code="SAVE10")
    db.flush()

    with pytest.raises(CouponInvalidError):
        coupon_service.resolve_and_validate(
            db,
            "SAVE10",
            location_id=loc_a.id,  # resolving for A while the coupon belongs to B
            pre_coupon_total=100000,
            customer_key="9876543210",
            booking_id=None,
            on=date.today(),
        )


def test_inactive_coupon_is_rejected(db: Session) -> None:
    """An is_active=False coupon raises CouponInvalidError."""
    loc = make_location(db)
    make_coupon(db, loc.id, code="SAVE10", is_active=False)
    db.flush()

    with pytest.raises(CouponInvalidError):
        coupon_service.resolve_and_validate(
            db,
            "SAVE10",
            location_id=loc.id,
            pre_coupon_total=100000,
            customer_key="9876543210",
            booking_id=None,
            on=date.today(),
        )


def test_out_of_window_coupon_is_rejected(db: Session) -> None:
    """A coupon whose validity window ended in the past raises CouponInvalidError."""
    loc = make_location(db)
    make_coupon(
        db,
        loc.id,
        code="SAVE10",
        effective_to=date.today() - timedelta(days=1),
    )
    db.flush()

    with pytest.raises(CouponInvalidError):
        coupon_service.resolve_and_validate(
            db,
            "SAVE10",
            location_id=loc.id,
            pre_coupon_total=100000,
            customer_key="9876543210",
            booking_id=None,
            on=date.today(),
        )
