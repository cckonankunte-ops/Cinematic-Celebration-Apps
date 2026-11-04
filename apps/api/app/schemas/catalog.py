"""Public catalog read schemas.

Prices are the actual chargeable price in paise (plan discount applied
server-side when give_discount is true). The UI converts paise to rupees.
"""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel


class LocationRead(BaseModel):
    id: int
    name: str
    slug: str
    address: str | None
    phone: str | None
    map_url: str | None = None
    # Working hours + online-booking policy (IST "HH:MM"). closes_at may be
    # earlier than opens_at, meaning close is the next day.
    opens_at: time | None = None
    closes_at: time | None = None
    last_online_booking_start: time | None = None
    allow_late_booking: bool = False
    # 'slot' (pick a configured slot) | 'open' (pick start+duration directly).
    booking_mode: str = "slot"


class PlanRead(BaseModel):
    id: int
    location_id: int
    title: str
    description: str | None
    details: str | None
    plan_type: int
    # list_price_paise = plan.price_paise; price_paise = actual chargeable (discount applied)
    list_price_paise: int
    price_paise: int
    people_allowed: int
    max_people_allowed: int
    extra_guest_paise: int
    advance_paise: int
    gallery_urls: list[str] = []


class SlotRead(BaseModel):
    id: int
    plan_id: int
    description: str
    # Machine-readable time (IST wall-clock, "HH:MM") + length in minutes. May be
    # null for legacy rows not yet backfilled; the UI falls back to description.
    start_time: time | None = None
    duration_minutes: int | None = None
    show_combos: bool
    sort_order: int


class SlotAvailabilityRead(SlotRead):
    """A slot plus whether it can still be booked for a given location/date.

    ``is_available`` is False when an active (pending|accepted) booking already
    holds this slot. The booking UIs render unavailable slots greyed-out and
    non-selectable; the database partial unique index remains the real guard
    against double booking.
    """

    is_available: bool


class PlanDurationRead(BaseModel):
    """A bookable duration for a plan (open mode) + its base price/advance."""

    duration_minutes: int
    price_paise: int
    advance_paise: int


class OpenAvailabilityRead(BaseModel):
    """A candidate start time for OPEN-mode booking + whether it's bookable.

    Generated for a (plan, location, date, duration) across the branch's working
    hours at :00/:30 steps. ``is_available`` is False when the start fails a time
    rule for the actor or its occupied window (incl. cleaning buffer) overlaps an
    active booking. The buffer is never exposed.
    """

    start_time: time
    is_available: bool


class CakeRead(BaseModel):
    id: int
    description: str
    price_paise: int
    image_url: str


class SpecialDecorRead(BaseModel):
    id: int
    name: str
    description: str
    price_paise: int
    image_url: str
    sort_order: int


class ComboRead(BaseModel):
    id: int
    name: str
    description: str
    price_paise: int
    image_url: str
    # Display-only savings. worth_paise is the combo's compare-at amount (None
    # when unset); savings_paise = max(0, worth - price), computed server-side.
    # Never affects what is charged; the client sends neither value.
    worth_paise: int | None = None
    savings_paise: int = 0


class OccasionRead(BaseModel):
    id: int
    name: str
