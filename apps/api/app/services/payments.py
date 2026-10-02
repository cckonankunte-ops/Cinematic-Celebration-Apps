"""Payment ledger service.

Payments are an append-only ledger. Amount due and paid status are DERIVED from
the ledger (never stored):
  amount_paid_paise = sum(payments.amount_paise)
  amount_due_paise  = total_paise - amount_paid_paise   (may be negative = overpaid)
  is_paid           = amount_paid_paise >= total_paise
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.security import CurrentUser, assert_location_access
from app.models.booking import Booking
from app.models.payment import Payment
from app.schemas.payment import DerivedAmounts, PaymentCreate
from app.services.events import write_booking_event


def amount_paid_paise(db: Session, booking_id: int) -> int:
    """Sum of all recorded payments for a booking (0 if none)."""
    total = db.execute(
        select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
            Payment.booking_id == booking_id
        )
    ).scalar_one()
    return int(total)


def derive_amounts(total_paise: int, paid_paise: int) -> DerivedAmounts:
    """Compute derived amounts from a booking total and its paid sum."""
    return DerivedAmounts(
        total_paise=total_paise,
        amount_paid_paise=paid_paise,
        amount_due_paise=total_paise - paid_paise,  # negative = overpaid
        is_paid=paid_paise >= total_paise,
    )


def derive_amounts_for_booking(db: Session, booking: Booking) -> DerivedAmounts:
    """Derived amounts for a booking using the current ledger."""
    return derive_amounts(booking.total_paise, amount_paid_paise(db, booking.id))


def record_payment(
    db: Session, booking_id: int, data: PaymentCreate, actor: CurrentUser
) -> Payment:
    """Append a payment and write a payment_recorded audit event, atomically."""
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found.")
    assert_location_access(actor, booking.location_id)

    payment = Payment(
        booking_id=booking_id,
        method=data.method,
        amount_paise=data.amount_paise,
        recorded_by_user_id=actor.id,
        provider=None,  # manual in Phase 1
        provider_ref=None,
        note=data.note,
    )
    if data.received_at is not None:
        payment.received_at = data.received_at
    db.add(payment)
    db.flush()  # assign received_at default + id

    write_booking_event(
        db,
        booking_id,
        "payment_recorded",
        actor_user_id=actor.id,
        new_value={"method": data.method, "amount_paise": data.amount_paise},
    )
    db.commit()
    db.refresh(payment)
    return payment


def list_payments(db: Session, booking_id: int) -> list[Payment]:
    """All ledger rows for a booking, oldest first."""
    return list(
        db.execute(
            select(Payment)
            .where(Payment.booking_id == booking_id)
            .order_by(Payment.received_at, Payment.id)
        ).scalars()
    )
