"""Booking request/response schemas.

The client sends only IDs, quantities, and customer details. All money is
computed server-side; any client-sent totals are ignored. Email is a plain
string (no email-validator dependency added in Phase 1).

Contact-field rule (R22, R23): on booking create/edit, phone is required and
must normalize to a valid Indian mobile; email is optional.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.phone import normalize_indian_mobile
from app.schemas.payment import PaymentRead


# --- Shared selection + breakdown schemas ---
class DecorSelectionIn(BaseModel):
    """One special-decor selection: an item id with a quantity (>= 1)."""

    id: int
    quantity: int = Field(ge=1)


class ComboSelectionIn(BaseModel):
    """One combo selection; combo quantity is always 1 (not accepted)."""

    id: int


class AddonLineRead(BaseModel):
    """One priced add-on line in a breakdown (cake/decor/combo/led)."""

    kind: str
    item_id: int | None
    name_snapshot: str
    unit_price_paise: int
    quantity: int
    weight_half_kg: int | None
    amount_paise: int
    combo_base_paise: int | None = None
    cake_upgrade_paise: int | None = None
    led_upgrade_paise: int | None = None


class PriceBreakdownRead(BaseModel):
    """Full server-computed price breakdown (preview and detail)."""

    plan_price_paise: int
    extra_guest_paise: int
    addon_lines: list[AddonLineRead]
    subtotal_paise: int
    discount_paise: int
    food_paise: int
    other_paise: int
    cleaning_paise: int
    coupon_code: str | None
    coupon_discount_paise: int
    total_paise: int
    amount_paid_paise: int
    amount_due_paise: int


# --- Preview request schemas ---
class PreviewBase(BaseModel):
    """Shared preview request shape (compute, never persist)."""

    location_id: int
    plan_id: int
    slot_id: int
    booking_date: date
    people: int = Field(ge=1)
    cake_id: int | None = None
    cake_weight_half_kg: int = Field(default=1, ge=1)
    special_decor: list[DecorSelectionIn] = Field(default_factory=list)
    combos: list[ComboSelectionIn] = Field(default_factory=list)
    led_name: str | None = None
    occasion_id: int | None = None
    coupon_code: str | None = None


class AdminPreviewRequest(PreviewBase):
    """Admin preview: may include the admin money fields."""

    booking_id: int | None = None  # exclude own redemption when previewing an edit
    discount_paise: int = Field(default=0, ge=0)
    food_paise: int = Field(default=0, ge=0)
    other_paise: int = Field(default=0, ge=0)
    cleaning_paise: int = Field(default=0, ge=0)


class PublicPreviewRequest(PreviewBase):
    """Public preview: no money fields; discount forced to 0 server-side."""

    pass


class BookingCreate(BaseModel):
    """Public customer booking request (IDs + details only, no money)."""

    location_id: int
    plan_id: int
    slot_id: int
    booking_date: date
    booking_name: str
    phone: str = Field(min_length=1)  # REQUIRED; validated as Indian mobile below
    email: str | None = None  # optional (was required)
    special_person_name: str | None = None
    name_on_cake: str | None = None
    message: str | None = None
    people: int = Field(ge=1)
    occasion_id: int | None = None
    cake_id: int | None = None
    cake_weight_half_kg: int = Field(default=1, ge=1)
    special_decor: list[DecorSelectionIn] = Field(default_factory=list)
    combos: list[ComboSelectionIn] = Field(default_factory=list)
    led_name: str | None = None
    coupon_code: str | None = None

    @field_validator("phone")
    @classmethod
    def _valid_indian_mobile(cls, v: str) -> str:
        # blank already rejected by min_length=1; non-normalizable -> 422
        if normalize_indian_mobile(v) is None:
            raise ValueError("phone must be a valid Indian mobile number")
        return v  # store the raw value; normalize on demand


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


class AdminBookingCreate(BookingCreate):
    """Admin/staff booking creation; adds optional extra charges."""

    discount_paise: int = Field(default=0, ge=0)
    food_paise: int = Field(default=0, ge=0)
    other_paise: int = Field(default=0, ge=0)
    cleaning_paise: int = Field(default=0, ge=0)
    # Optional advance recorded as the first ledger payment in the SAME
    # transaction as the booking insert. Overpayment is allowed (may exceed the
    # total); when None, no payment is recorded.
    advance_amount_paise: int | None = Field(default=None, gt=0)
    advance_method: Literal["cash", "upi", "card", "other"] | None = None


class BookingUpdate(BaseModel):
    """Partial update for an existing booking (all fields optional)."""

    people: int | None = Field(default=None, ge=1)
    occasion_id: int | None = None
    cake_id: int | None = None
    cake_weight_half_kg: int | None = Field(default=None, ge=1)
    special_decor: list[DecorSelectionIn] | None = None
    combos: list[ComboSelectionIn] | None = None
    led_name: str | None = None
    coupon_code: str | None = None
    discount_paise: int | None = Field(default=None, ge=0)
    food_paise: int | None = Field(default=None, ge=0)
    other_paise: int | None = Field(default=None, ge=0)
    cleaning_paise: int | None = Field(default=None, ge=0)
    booking_name: str | None = None
    phone: str | None = None  # None = unchanged; if present, must be valid Indian mobile
    email: str | None = None  # None = unchanged; email remains optional
    special_person_name: str | None = None
    name_on_cake: str | None = None
    message: str | None = None

    @field_validator("phone")
    @classmethod
    def _valid_indian_mobile_if_present(cls, v: str | None) -> str | None:
        if v is None:
            return None  # unchanged
        if not v.strip() or normalize_indian_mobile(v) is None:
            raise ValueError("phone must be a valid Indian mobile number")
        return v


class BookingItemRead(BaseModel):
    """One add-on line item snapshot for a booking."""

    kind: str
    item_id: int | None
    name_snapshot: str
    price_paise: int
    quantity: int
    weight_half_kg: int | None


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
    email: str | None
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
    led_name: str | None
    coupon_code: str | None
    coupon_discount_paise: int
    total_paise: int
    advance_paise: int
    amount_paid_paise: int
    amount_due_paise: int  # may be negative = overpaid
    is_paid: bool
    items: list[BookingItemRead]
    payments: list[PaymentRead]
    created_at: datetime


class BookingListItem(BaseModel):
    """Booking row for the admin list view.

    Carries the main columns staff expect from the legacy bookings grid: the
    plan/slot/occasion labels, the special-person name, the discount, the
    special-decor and cake names, and the created-at timestamp — alongside the
    reference, guest count, and the derived payment amounts.
    """

    id: int
    booking_reference: str
    booking_date: date
    status: str
    booking_name: str
    phone: str | None = None
    special_person_name: str | None = None
    people: int
    plan_title: str
    slot_description: str
    occasion_name: str | None = None
    special_decor: list[str] = []
    cakes: list[str] = []
    combos: list[str] = []
    discount_paise: int
    total_paise: int
    advance_paise: int
    amount_paid_paise: int
    amount_due_paise: int
    is_paid: bool
    created_at: datetime


class AcceptBookingRequest(BaseModel):
    """Body for the accept endpoint; admin-only advance override."""

    override_advance: bool = False
