"""Public booking endpoints: create a booking request and look up status.

Thin router: parse Pydantic input, call one booking-service function, return a
schema. All money and validation live in the service layer. Booking creation is
rate-limited to deter abuse; the status lookup is read-only with no external
calls.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.ratelimit import limiter
from app.schemas.booking import BookingCreate, CustomerBookingResult, PublicBookingStatus
from app.services import booking as booking_service
from app.services import catalog as catalog_service
from app.services.payments import derive_amounts_for_booking

router = APIRouter(prefix="/api/v1/public", tags=["public-bookings"])


@router.post(
    "/bookings",
    response_model=CustomerBookingResult,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
def create_booking(
    request: Request,
    body: BookingCreate = Body(...),
    db: Session = Depends(get_db),
) -> CustomerBookingResult:
    """Create a pending customer booking request (holds the slot)."""
    return booking_service.create_customer_booking(db, body)


@router.get("/bookings/{public_token}", response_model=PublicBookingStatus)
@limiter.limit("30/minute")
def get_booking_status(
    request: Request,
    public_token: str,
    db: Session = Depends(get_db),
) -> PublicBookingStatus:
    """Read-only booking status lookup by public token (no external calls)."""
    booking = booking_service.get_booking_by_token(db, public_token)
    amounts = derive_amounts_for_booking(db, booking)
    plan_title, slot_description = catalog_service.booking_plan_and_slot_labels(
        db, booking.plan_id, booking.slot_id
    )
    return PublicBookingStatus(
        status=booking.status,
        booking_name=booking.booking_name,
        plan_title=plan_title,
        slot_description=slot_description,
        booking_date=booking.booking_date,
        total_paise=amounts.total_paise,
        amount_paid_paise=amounts.amount_paid_paise,
        amount_due_paise=amounts.amount_due_paise,
        is_paid=amounts.is_paid,
    )
