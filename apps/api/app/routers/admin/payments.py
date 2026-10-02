"""Admin payment ledger endpoints (admin + staff).

Thin router over the payments service. Location access is enforced in the
service layer so staff only touch bookings for their assigned location.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, check_origin, require_role
from app.schemas.payment import PaymentCreate, PaymentRead
from app.services import booking as booking_service
from app.services import payments as payments_service

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-payments"],
    dependencies=[Depends(require_role("admin", "staff")), Depends(check_origin)],
)


def _to_payment_read(payment: object) -> PaymentRead:
    return PaymentRead.model_validate(payment, from_attributes=True)


@router.get("/bookings/{booking_id}/payments", response_model=list[PaymentRead])
def list_payments(
    booking_id: int,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> list[PaymentRead]:
    # Enforce location access by loading the booking through the service.
    booking_service.get_booking(db, booking_id, actor)
    return [_to_payment_read(p) for p in payments_service.list_payments(db, booking_id)]


@router.post(
    "/bookings/{booking_id}/payments",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
def record_payment(
    booking_id: int,
    body: PaymentCreate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> PaymentRead:
    payment = payments_service.record_payment(db, booking_id, body, actor)
    return _to_payment_read(payment)
