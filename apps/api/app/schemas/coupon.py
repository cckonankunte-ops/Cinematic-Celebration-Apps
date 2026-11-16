"""Coupon authoring schemas (admin-only, location-scoped).

Coupons are server-authoritative: the client sends only the code; the server
validates and computes the discount. Flat or percentage with an optional cap,
a configurable percentage base, and selectable usage limits.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CouponComponents(BaseModel):
    """Component selection; only meaningful for selected_components base."""

    plan: bool = False
    extra_guest: bool = False
    decor: bool = False
    combos: bool = False
    cake: bool = False
    food: bool = False


class CouponBase(BaseModel):
    code: str = Field(min_length=1)
    # Admin-written, customer-facing offer label + blurb (plain text). Shown on
    # the home page only when is_public is true. Display-only; never affect math.
    name: str | None = None
    description: str | None = None
    is_public: bool = False
    type: Literal["flat", "percentage"]
    value: int = Field(ge=0)
    cap_paise: int | None = Field(default=None, ge=0)
    percentage_base: Literal["total", "selected_components"] = "total"
    components: CouponComponents | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool = True
    one_time: bool = False
    total_usage_limit: int | None = Field(default=None, ge=1)
    per_customer_limit: int | None = Field(default=None, ge=1)
    min_order_paise: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check(self) -> CouponBase:
        if self.type == "percentage" and not (0 <= self.value <= 100):
            raise ValueError("percentage value must be 0..100")
        return self


class CouponCreate(CouponBase):
    location_id: int


class CouponUpdate(CouponBase):
    pass


class CouponRead(CouponBase):
    id: int
    location_id: int


class PublicOfferRead(BaseModel):
    """Safe, customer-facing coupon offer for the home-page showcase.

    Only public, display-safe fields — never usage limits, caps, value, or
    percentage-base internals.
    """

    code: str
    name: str | None
    description: str | None
    effective_from: date | None
    effective_to: date | None
