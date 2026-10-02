"""Booking request/response schemas.

The client sends only IDs, quantities, and customer details. All money is
computed server-side; any client-sent totals are ignored. Email is a plain
string (no email-validator dependency added in Phase 1).
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class BookingCreate(BaseModel):
    """Public customer booking request (IDs + details only, no money)."""

    location_id: int
    plan_id: int
    slot_id: int
    booking_date: date
    booking_name: str
    email: str
    phone: str | None = None
    special_person_name: str | None = None
    name_on_cake: str | None = None
    message: str | None = None
    people: int = Field(ge=1)
    occasion_id: int | None = None
    cake_id: int | None = None
    special_decor_ids: list[int] = Field(default_factory=list)
    combo_ids: list[int] = Field(default_factory=list)


class CustomerBookingResult(BaseModel):
    """Response for a created customer booking request."""

    booking_token: str
    advance_paise: int
    payment_instructions: str


class PublicBookingStatus(BaseModel):
    """Read-only booking status looked up by public token."""

    status: str
    booking_name: str
    plan_title: str
    slot_description: str
    booking_date: date
    total_paise: int
    amount_paid_paise: int
    amount_due_paise: int  # may be negative = overpaid
    is_paid: bool


class ContactCreate(BaseModel):
    """Public contact form submission."""

    name: str
    phone: str
    email: str
    message: str


class ContactResult(BaseModel):
    """Response for a saved contact lead."""

    message: str


class AdminBookingCreate(BaseModel):
    """Admin/staff booking creation (IDs + details + optional extra charges)."""

    location_id: int
    plan_id: int
    slot_id: int
    booking_date: date
    booking_name: str
    email: str
    phone: str | None = None
    special_person_name: str | None = None
    name_on_cake: str | None = None
    message: str | None = None
    people: int = Field(ge=1)
    occasion_id: int | None = None
    cake_id: int | None = None
    special_decor_ids: list[int] = Field(default_factory=list)
    combo_ids: list[int] = Field(default_factory=list)
    discount_paise: int = Field(default=0, ge=0)
    food_paise: int = Field(default=0, ge=0)
    other_paise: int = Field(default=0, ge=0)
    cleaning_paise: int = Field(default=0, ge=0)


class BookingUpdate(BaseModel):
    """Partial update for an existing booking (all fields optional)."""

    people: int | None = Field(default=None, ge=1)
    occasion_id: int | None = None
    cake_id: int | None = None
    special_decor_ids: list[int] | None = None
    combo_ids: list[int] | None = None
    discount_paise: int | None = Field(default=None, ge=0)
    food_paise: int | None = Field(default=None, ge=0)
    other_paise: int | None = Field(default=None, ge=0)
    cleaning_paise: int | None = Field(default=None, ge=0)
    booking_name: str | None = None
    phone: str | None = None
    special_person_name: str | None = None
    name_on_cake: str | None = None
    message: str | None = None


class BookingItemRead(BaseModel):
    """One add-on line item snapshot for a booking."""

    kind: str
    item_id: int | None
    name_snapshot: str
    price_paise: int


class BookingRead(BaseModel):
    """Full booking detail with derived amounts and add-on items."""

    id: int
    booking_reference: str
    public_token: str
    location_id: int
    plan_id: int
    slot_id: int
    booking_date: date
    status: str
    booking_name: str
    email: str
    phone: str | None
    people: int
    occasion_id: int | None
    plan_price_paise: int
    extra_guest_paise: int
    subtotal_paise: int
    discount_paise: int
    food_paise: int
    other_paise: int
    cleaning_paise: int
    total_paise: int
    advance_paise: int
    amount_paid_paise: int
    amount_due_paise: int  # may be negative = overpaid
    is_paid: bool
    items: list[BookingItemRead]
    created_at: datetime


class BookingListItem(BaseModel):
    """Lighter booking row for list views."""

    id: int
    booking_reference: str
    booking_date: date
    status: str
    booking_name: str
    people: int
    total_paise: int
    advance_paise: int
    amount_paid_paise: int
    amount_due_paise: int
    is_paid: bool


class AcceptBookingRequest(BaseModel):
    """Body for the accept endpoint; admin-only advance override."""

    override_advance: bool = False
