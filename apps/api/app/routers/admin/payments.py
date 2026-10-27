"""Admin payment ledger endpoints (admin + staff).

Thin router over the payments service. Location access is enforced in the
service layer so staff only touch bookings for their assigned location.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import NotFoundError
from app.core.security import CurrentUser, check_origin, require_role
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate, PaymentRead, PaymentVoidRequest
from app.services import booking as booking_service
from app.services import payments as payments_service

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-payments"],
    dependencies=[Depends(require_role("admin", "staff")), Depends(check_origin)],
)


@router.get("/bookings/{booking_id}/payments", response_model=list[PaymentRead])
def list_payments(
    booking_id: int,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> list[PaymentRead]:
    # Enforce location access by loading the booking through the service.
    booking_service.get_booking(db, booking_id, actor)
    return payments_service.to_payment_reads(
        payments_service.list_payments(db, booking_id)
    )


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
    return payments_service.to_payment_reads([payment])[0]


@router.post("/payments/{payment_id}/void", response_model=list[PaymentRead])
def void_payment(
    payment_id: int,
    body: PaymentVoidRequest,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> list[PaymentRead]:
    # Recover booking_id from the payment; void_payment re-checks admin + ownership.
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise NotFoundError("Payment not found.")
    ledger = payments_service.void_payment(
        db, payment.booking_id, payment_id, reason=body.reason, actor=actor
    )
    return payments_service.to_payment_reads(ledger)
