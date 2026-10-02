"""Admin catalog write schemas.

Create/Update request models and admin-facing read models that expose
is_active and the effective_from/effective_to validity window (admins manage
inactive items too). Money fields are integer paise (>= 0). Update schemas have
all-optional fields for partial updates.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


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
    description: str = Field(min_length=1)
    show_combos: bool = True
    sort_order: int = Field(ge=0, default=0)
    effective_from: date
    effective_to: date | None = None


class SlotUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1)
    show_combos: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None


class SlotAdminRead(BaseModel):
    id: int
    plan_id: int
    description: str
    show_combos: bool
    sort_order: int
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
    description: str = Field(min_length=1)
    price_paise: int = Field(ge=0)
    object_key: str = Field(min_length=1)
    effective_from: date
    effective_to: date | None = None


class ComboUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    price_paise: int | None = Field(default=None, ge=0)
    object_key: str | None = Field(default=None, min_length=1)
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
