"""Public catalog read schemas.

Prices are the actual chargeable price in paise (plan discount applied
server-side when give_discount is true). The UI converts paise to rupees.
"""

from __future__ import annotations

from pydantic import BaseModel


class LocationRead(BaseModel):
    id: int
    name: str
    slug: str
    address: str | None
    phone: str | None


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
    show_combos: bool
    sort_order: int


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


class OccasionRead(BaseModel):
    id: int
    name: str
