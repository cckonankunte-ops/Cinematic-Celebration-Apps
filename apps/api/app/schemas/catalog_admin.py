"""Admin catalog write schemas.

Create/Update request models and admin-facing read models that expose
is_active and the effective_from/effective_to validity window (admins manage
inactive items too). Money fields are integer paise (>= 0). Update schemas have
all-optional fields for partial updates.
"""

from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _validate_half_hour(value: time) -> time:
    """Start times must be on the hour or half-hour with zero seconds."""
    if value.minute not in (0, 30) or value.second != 0 or value.microsecond != 0:
        raise ValueError("Start time must be on the hour or half-hour (e.g. 3:00 or 3:30).")
    return value


# --- Plans ---
class PlanCreate(BaseModel):
    location_id: int
    title: str = Field(min_length=1)
    description: str | None = None
    details: str | None = None
    plan_type: int
    price_paise: int = Field(ge=0)
    people_allowed: int = Field(ge=0, default=4)
    max_people_allowed: int = Field(ge=0)
    extra_guest_paise: int = Field(ge=0, default=0)
    give_discount: bool = False
    max_discount_paise: int = Field(ge=0, default=0)
    advance_paise: int = Field(ge=0, default=0)
    effective_from: date
    effective_to: date | None = None


class PlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    details: str | None = None
    plan_type: int | None = None
    price_paise: int | None = Field(default=None, ge=0)
    people_allowed: int | None = Field(default=None, ge=0)
    max_people_allowed: int | None = Field(default=None, ge=0)
    extra_guest_paise: int | None = Field(default=None, ge=0)
    give_discount: bool | None = None
    max_discount_paise: int | None = Field(default=None, ge=0)
    advance_paise: int | None = Field(default=None, ge=0)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class PlanAdminRead(BaseModel):
    id: int
    location_id: int
    title: str
    description: str | None
    details: str | None
    plan_type: int
    price_paise: int
    people_allowed: int
    max_people_allowed: int
    extra_guest_paise: int
    give_discount: bool
    max_discount_paise: int
    advance_paise: int
    effective_from: date
    effective_to: date
    is_active: bool


# --- Slots ---
class SlotCreate(BaseModel):
    plan_id: int
    # Machine-readable time (IST). Start must be on the hour/half-hour.
    start_time: time
    duration_minutes: int = Field(gt=0)
    # Optional label; derived from start+duration when blank.
    description: str = ""
    show_combos: bool = True
    sort_order: int = Field(ge=0, default=0)
    effective_from: date
    effective_to: date | None = None

    _check_start = field_validator("start_time")(_validate_half_hour)


class SlotUpdate(BaseModel):
    start_time: time | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None)
    show_combos: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None

    @field_validator("start_time")
    @classmethod
    def _check_start(cls, value: time | None) -> time | None:
        return _validate_half_hour(value) if value is not None else None


class SlotAdminRead(BaseModel):
    id: int
    plan_id: int
    start_time: time | None
    duration_minutes: int | None
    description: str
    show_combos: bool
    sort_order: int
    effective_from: date
    effective_to: date
    is_active: bool


# --- Location working hours + online-booking policy ---
class LocationHoursUpdate(BaseModel):
    opens_at: time | None = None
    closes_at: time | None = None
    last_online_booking_start: time | None = None
    allow_late_booking: bool | None = None
    booking_mode: Literal["slot", "open"] | None = None


class LocationAdminRead(BaseModel):
    id: int
    name: str
    slug: str
    opens_at: time
    closes_at: time
    last_online_booking_start: time
    allow_late_booking: bool
    booking_mode: str
    is_active: bool


# --- Plan pricing (per-duration base price + advance, R11) ---
class PlanPricingCreate(BaseModel):
    plan_id: int
    duration_minutes: int = Field(gt=0)
    price_paise: int = Field(ge=0)
    advance_paise: int = Field(ge=0, default=0)
    effective_from: date
    effective_to: date | None = None


class PlanPricingUpdate(BaseModel):
    price_paise: int | None = Field(default=None, ge=0)
    advance_paise: int | None = Field(default=None, ge=0)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class PlanPricingAdminRead(BaseModel):
    id: int
    plan_id: int
    duration_minutes: int
    price_paise: int
    advance_paise: int
    effective_from: date
    effective_to: date
    is_active: bool


# --- Cakes ---
class CakeCreate(BaseModel):
    location_id: int
    description: str = Field(min_length=1)
    price_paise: int = Field(ge=0)
    object_key: str = Field(min_length=1)
    effective_from: date
    effective_to: date | None = None


class CakeUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1)
    price_paise: int | None = Field(default=None, ge=0)
    object_key: str | None = Field(default=None, min_length=1)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class CakeAdminRead(BaseModel):
    id: int
    location_id: int
    description: str
    price_paise: int
    object_key: str
    image_url: str
    effective_from: date
    effective_to: date
    is_active: bool


# --- Special decor ---
class SpecialDecorCreate(BaseModel):
    location_id: int
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    price_paise: int = Field(ge=0)
    object_key: str = Field(min_length=1)
    sort_order: int = Field(ge=0, default=0)
    effective_from: date
    effective_to: date | None = None


class SpecialDecorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    price_paise: int | None = Field(default=None, ge=0)
    object_key: str | None = Field(default=None, min_length=1)
    sort_order: int | None = Field(default=None, ge=0)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class SpecialDecorAdminRead(BaseModel):
    id: int
    location_id: int
    name: str
    description: str
    price_paise: int
    object_key: str
    image_url: str
    sort_order: int
    effective_from: date
    effective_to: date
    is_active: bool


# --- Combos ---
class ComboCreate(BaseModel):
    location_id: int
    name: str = Field(min_length=1)
    # A combo is defined by name + price + optional cake/LED baselines; it is
    # not an image tile like cakes/decor. Description and object_key are
    # optional so a combo can be created without an image, while the DB's
    # NOT NULL object_key is satisfied by a sensible default.
    description: str = ""
    price_paise: int = Field(ge=0)
    object_key: str = "combo"
    cake_baseline_paise: int | None = Field(default=None, ge=0)
    led_baseline_paise: int | None = Field(default=None, ge=0)
    # Display-only "worth"/compare-at amount (paise); None = no savings shown.
    compare_at_paise: int | None = Field(default=None, ge=0)
    effective_from: date
    effective_to: date | None = None


class ComboUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    price_paise: int | None = Field(default=None, ge=0)
    object_key: str | None = Field(default=None, min_length=1)
    cake_baseline_paise: int | None = Field(default=None, ge=0)
    led_baseline_paise: int | None = Field(default=None, ge=0)
    compare_at_paise: int | None = Field(default=None, ge=0)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class ComboAdminRead(BaseModel):
    id: int
    location_id: int
    name: str
    description: str
    price_paise: int
    object_key: str
    image_url: str
    cake_baseline_paise: int | None
    led_baseline_paise: int | None
    # Display-only worth + derived saving = max(0, worth - price).
    compare_at_paise: int | None
    savings_paise: int
    effective_from: date
    effective_to: date
    is_active: bool


# --- Users ---
class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=250)
    password: str = Field(min_length=8, max_length=1024)
    role: Literal["admin", "staff"]
    location_id: int | None = None


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=250)
    password: str | None = Field(default=None, min_length=8, max_length=1024)
    role: Literal["admin", "staff"] | None = None
    location_id: int | None = None
    is_active: bool | None = None


class UserAdminRead(BaseModel):
    id: int
    username: str
    role: str
    location_id: int | None
    is_active: bool


# --- Plan gallery ---
class GalleryUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(ge=0, default=0)


class GalleryImageRead(BaseModel):
    id: int
    plan_id: int
    object_key: str
    image_url: str
    sort_order: int
    upload_url: str | None = None


# --- Catalog add-on image uploads (cake / decor / combo) ---
class CatalogImageUploadRequest(BaseModel):
    """Request a presigned PUT URL for a cake/decor/combo image.

    Returns an object key + upload URL WITHOUT creating any row; the caller
    uploads the file, then includes the object_key in the entity's create/update.
    """

    kind: Literal["cake", "decor", "combo"]
    filename: str = Field(min_length=1, max_length=255)


class CatalogImageUploadRead(BaseModel):
    object_key: str
    upload_url: str
