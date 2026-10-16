"""Coupon resolution, validation, and redemption tracking (IO-bound).

Pricing receives only the pure ValidatedCoupon value object; all DB access and
limit enforcement live here. resolve_and_validate performs NO writes;
record_redemption upserts the single per-booking redemption row.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import CouponInvalidError, CouponNotApplicableError
from app.models.coupon import Coupon
from app.models.coupon_redemption import CouponRedemption
from app.services.pricing import COMPONENT_KEYS, ValidatedCoupon


def resolve_coupon_row(db: Session, *, location_id: int, code: str) -> Coupon:
    """Fetch the location-scoped coupon row by exact code (step 1).

    Raises CouponInvalidError when no coupon with that code exists for the
    location (a coupon from another location is a non-match). Returned so the
    booking service can fetch the row once and pass it to record_redemption.
    """
    coupon = db.execute(
        select(Coupon).where(
            Coupon.location_id == location_id,
            Coupon.code == code,
        )
    ).scalar_one_or_none()
    if coupon is None:
        raise CouponInvalidError("Coupon code is not valid for this location.")
    return coupon


def _redemption_count(
    db: Session,
    coupon_id: int,
    *,
    booking_id: int | None,
    customer_key: str | None = None,
) -> int:
    """Count redemptions for a coupon, excluding this booking's own row.

    When booking_id is None nothing is excluded. When customer_key is provided
    the count is restricted to that customer (for the per-customer limit).
    """
    stmt = select(func.count()).select_from(CouponRedemption).where(
        CouponRedemption.coupon_id == coupon_id
    )
    if booking_id is not None:
        stmt = stmt.where(CouponRedemption.booking_id != booking_id)
    if customer_key is not None:
        stmt = stmt.where(CouponRedemption.customer_key == customer_key)
    return int(db.execute(stmt).scalar_one())


def resolve_and_validate(
    db: Session,
    code: str,
    *,
    location_id: int,
    pre_coupon_total: int,
    customer_key: str,
    booking_id: int | None = None,
    on: date | None = None,
) -> ValidatedCoupon:
    """Resolve a coupon code within a location and enforce every enabled limit.

    Raises CouponInvalidError (422 COUPON_INVALID) when the code is unknown for
    the location, inactive, or outside its validity window; raises
    CouponNotApplicableError (422 COUPON_NOT_APPLICABLE) when an enabled usage
    limit would be violated. Returns a pure ValidatedCoupon on success. Does NOT
    write anything (the redemption is recorded separately, in the same tx).

    ``on`` is the date used for the validity-window check; defaults to today so
    the function is usable from a preview that has no booking_date yet.
    """
    check_date = on if on is not None else date.today()

    # Step 1 — Location match + existence.
    coupon = resolve_coupon_row(db, location_id=location_id, code=code)

    # Step 2 — Active.
    if not coupon.is_active:
        raise CouponInvalidError("This coupon is no longer active.")

    # Step 3 — Validity window.
    if (coupon.effective_from is not None and check_date < coupon.effective_from) or (
        coupon.effective_to is not None and check_date > coupon.effective_to
    ):
        raise CouponInvalidError("This coupon is outside its validity window.")

    # Step 4 — Minimum order.
    if coupon.min_order_paise is not None and pre_coupon_total < coupon.min_order_paise:
        raise CouponNotApplicableError(
            "Order total is below the minimum for this coupon."
        )

    # Step 5 — Usage limits (each excluding this booking's own existing row).
    effective_total_limit = 1 if coupon.one_time else coupon.total_usage_limit
    if effective_total_limit is not None:
        total_count = _redemption_count(db, coupon.id, booking_id=booking_id)
        if total_count >= effective_total_limit:
            raise CouponNotApplicableError(
                "This coupon has reached its usage limit."
            )

    if coupon.per_customer_limit is not None:
        customer_count = _redemption_count(
            db, coupon.id, booking_id=booking_id, customer_key=customer_key
        )
        if customer_count >= coupon.per_customer_limit:
            raise CouponNotApplicableError(
                "You have already used this coupon the maximum number of times."
            )

    # On success, build the pure value object pricing consumes.
    if coupon.percentage_base == "selected_components":
        components = frozenset(
            k for k, v in (coupon.components or {}).items() if v
        ) & COMPONENT_KEYS
    else:
        components = frozenset()

    return ValidatedCoupon(
        code=coupon.code,
        type=coupon.type,
        value=coupon.value,
        cap_paise=coupon.cap_paise,
        percentage_base=coupon.percentage_base,
        components=components,
    )


def record_redemption(
    db: Session,
    coupon_row: Coupon,
    *,
    booking_id: int,
    customer_key: str,
    discount_paise: int,
) -> None:
    """Upsert the coupon_redemptions row keyed on booking_id.

    Because coupon_redemptions.booking_id is unique, re-editing the same booking
    UPSERTs its own redemption row (updates discount_paise) rather than
    inserting a second — so an edit never consumes a second use of the coupon
    for the same booking. Uses db.flush() (not commit); it runs inside the
    booking save's open transaction, matching the write_booking_event
    convention.
    """
    existing = db.execute(
        select(CouponRedemption).where(CouponRedemption.booking_id == booking_id)
    ).scalar_one_or_none()
    if existing is not None:
        existing.coupon_id = coupon_row.id
        existing.customer_key = customer_key
        existing.discount_paise = discount_paise
    else:
        db.add(
            CouponRedemption(
                coupon_id=coupon_row.id,
                booking_id=booking_id,
                customer_key=customer_key,
                discount_paise=discount_paise,
            )
        )
    db.flush()
