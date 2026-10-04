"""Admin booking management endpoints (admin + staff).

Thin router: parse Pydantic input, call one booking-service function, return a
schema. Location access is enforced in the service layer, so staff are limited
to their assigned location. The confirmation email on accept is scheduled via
BackgroundTasks (which opens its own session after the response).
"""

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, check_origin, require_role
from app.models.booking import Booking
from app.schemas.booking import (
    AcceptBookingRequest,
    AdminBookingCreate,
    BookingItemRead,
    BookingListItem,
    BookingRead,
    BookingUpdate,
)
from app.services import booking as booking_service
from app.services import email as email_service
from app.services import payments as payments_service

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-bookings"],
    dependencies=[Depends(require_role("admin", "staff")), Depends(check_origin)],
)


def to_booking_read(db: Session, booking: Booking) -> BookingRead:
    """Assemble a BookingRead with derived amounts and add-on items."""
    amounts = payments_service.derive_amounts_for_booking(db, booking)
    items = [
        BookingItemRead(
            kind=item.kind,
            item_id=item.item_id,
            name_snapshot=item.name_snapshot,
            price_paise=item.price_paise,
        )
        for item in booking_service.list_booking_items(db, booking.id)
    ]
    return BookingRead(
        id=booking.id,
        booking_reference=booking.booking_reference,
        public_token=booking.public_token,
        location_id=booking.location_id,
        plan_id=booking.plan_id,
        slot_id=booking.slot_id,
        booking_date=booking.booking_date,
        status=booking.status,
        booking_name=booking.booking_name,
        email=booking.email,
        phone=booking.phone,
        people=booking.people,
        occasion_id=booking.occasion_id,
        plan_price_paise=booking.plan_price_paise,
        extra_guest_paise=booking.extra_guest_paise,
        subtotal_paise=booking.subtotal_paise,
        discount_paise=booking.discount_paise,
        food_paise=booking.food_paise,
        other_paise=booking.other_paise,
        cleaning_paise=booking.cleaning_paise,
        total_paise=booking.total_paise,
        advance_paise=booking.advance_paise,
        amount_paid_paise=amounts.amount_paid_paise,
        amount_due_paise=amounts.amount_due_paise,
        is_paid=amounts.is_paid,
        items=items,
        created_at=booking.created_at,
    )


def _to_list_item(db: Session, booking: Booking) -> BookingListItem:
    amounts = payments_service.derive_amounts_for_booking(db, booking)
    return BookingListItem(
        id=booking.id,
        booking_reference=booking.booking_reference,
        booking_date=booking.booking_date,
        status=booking.status,
        booking_name=booking.booking_name,
        people=booking.people,
        total_paise=booking.total_paise,
        advance_paise=booking.advance_paise,
        amount_paid_paise=amounts.amount_paid_paise,
        amount_due_paise=amounts.amount_due_paise,
        is_paid=amounts.is_paid,
    )


@router.get("/bookings", response_model=list[BookingListItem])
def list_bookings(
    location_id: int,
    booking_date: date | None = Query(default=None, alias="date"),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> list[BookingListItem]:
    bookings = booking_service.list_bookings(
        db, actor, location_id=location_id, on=booking_date, status=status_filter
    )
    return [_to_list_item(db, b) for b in bookings]


@router.post("/bookings", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(
    body: AdminBookingCreate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> BookingRead:
    booking = booking_service.create_admin_booking(db, body, actor)
    return to_booking_read(db, booking)


@router.get("/bookings/{booking_id}", response_model=BookingRead)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> BookingRead:
    booking = booking_service.get_booking(db, booking_id, actor)
    return to_booking_read(db, booking)


@router.patch("/bookings/{booking_id}", response_model=BookingRead)
def update_booking(
    booking_id: int,
    body: BookingUpdate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> BookingRead:
    booking = booking_service.update_booking(db, booking_id, body, actor)
    return to_booking_read(db, booking)


@router.post("/bookings/{booking_id}/accept", response_model=BookingRead)
def accept_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    body: AcceptBookingRequest | None = None,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> BookingRead:
    override = body.override_advance if body is not None else False
    booking = booking_service.accept_booking(
        db, booking_id, override_advance=override, actor=actor
    )
    if booking.confirmation_sent_at is None:
        background_tasks.add_task(email_service.send_confirmation, booking.id)
    return to_booking_read(db, booking)


@router.post("/bookings/{booking_id}/reject", response_model=BookingRead)
def reject_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> BookingRead:
    booking = booking_service.reject_booking(db, booking_id, actor=actor)
    return to_booking_read(db, booking)
