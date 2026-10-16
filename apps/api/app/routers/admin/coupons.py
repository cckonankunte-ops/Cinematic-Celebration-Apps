"""Admin coupon authoring endpoints (admin-only).

Thin router over the coupon_admin service, mounted under the admin prefix with a
router-level ``require_role("admin")`` so every coupon endpoint is admin-only by
default (non-admin -> 403).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import check_origin, require_role
from app.schemas.coupon import CouponCreate, CouponRead, CouponUpdate
from app.services import coupon_admin

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-coupons"],
    dependencies=[Depends(require_role("admin")), Depends(check_origin)],
)


@router.get("/coupons", response_model=list[CouponRead])
def list_coupons(location_id: int, db: Session = Depends(get_db)) -> list[CouponRead]:
    return [coupon_admin.to_coupon_read(c) for c in coupon_admin.list_coupons(db, location_id)]


@router.post("/coupons", response_model=CouponRead, status_code=status.HTTP_201_CREATED)
def create_coupon(body: CouponCreate, db: Session = Depends(get_db)) -> CouponRead:
    return coupon_admin.to_coupon_read(coupon_admin.create_coupon(db, body))


@router.patch("/coupons/{coupon_id}", response_model=CouponRead)
def update_coupon(
    coupon_id: int, body: CouponUpdate, db: Session = Depends(get_db)
) -> CouponRead:
    return coupon_admin.to_coupon_read(coupon_admin.update_coupon(db, coupon_id, body))
