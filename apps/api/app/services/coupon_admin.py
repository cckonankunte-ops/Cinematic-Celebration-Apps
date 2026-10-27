"""Admin coupon authoring service (admin-only, location-scoped).

CRUD over the location-scoped Coupon rows. The (location_id, code) unique index
backs a friendly duplicate-code error. All validation (percentage range,
non-negative money) is enforced by the Pydantic schema before we reach here.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.coupon import Coupon
from app.schemas.coupon import CouponCreate, CouponRead, CouponUpdate


def _components_to_dict(components) -> dict | None:
    return components.model_dump() if components is not None else None


def create_coupon(db: Session, data: CouponCreate) -> Coupon:
    coupon = Coupon(
        location_id=data.location_id,
        code=data.code,
        type=data.type,
        value=data.value,
        cap_paise=data.cap_paise,
        percentage_base=data.percentage_base,
        components=_components_to_dict(data.components),
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        is_active=data.is_active,
        one_time=data.one_time,
        total_usage_limit=data.total_usage_limit,
        per_customer_limit=data.per_customer_limit,
        min_order_paise=data.min_order_paise,
    )
    db.add(coupon)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValidationFailedError(
            "A coupon with this code already exists for this location."
        ) from exc
    db.refresh(coupon)
    return coupon


def update_coupon(db: Session, coupon_id: int, data: CouponUpdate) -> Coupon:
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise NotFoundError("Coupon not found.")
    coupon.code = data.code
    coupon.type = data.type
    coupon.value = data.value
    coupon.cap_paise = data.cap_paise
    coupon.percentage_base = data.percentage_base
    coupon.components = _components_to_dict(data.components)
    coupon.effective_from = data.effective_from
    coupon.effective_to = data.effective_to
    coupon.is_active = data.is_active
    coupon.one_time = data.one_time
    coupon.total_usage_limit = data.total_usage_limit
    coupon.per_customer_limit = data.per_customer_limit
    coupon.min_order_paise = data.min_order_paise
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValidationFailedError(
            "A coupon with this code already exists for this location."
        ) from exc
    db.refresh(coupon)
    return coupon


def list_coupons(db: Session, location_id: int) -> list[Coupon]:
    return list(
        db.execute(
            select(Coupon)
            .where(Coupon.location_id == location_id)
            .order_by(Coupon.id)
        ).scalars()
    )


def to_coupon_read(coupon: Coupon) -> CouponRead:
    from app.schemas.coupon import CouponComponents

    components = CouponComponents(**coupon.components) if coupon.components else None
    return CouponRead(
        id=coupon.id,
        location_id=coupon.location_id,
        code=coupon.code,
        type=coupon.type,
        value=coupon.value,
        cap_paise=coupon.cap_paise,
        percentage_base=coupon.percentage_base,
        components=components,
        effective_from=coupon.effective_from,
        effective_to=coupon.effective_to,
        is_active=coupon.is_active,
        one_time=coupon.one_time,
        total_usage_limit=coupon.total_usage_limit,
        per_customer_limit=coupon.per_customer_limit,
        min_order_paise=coupon.min_order_paise,
    )
