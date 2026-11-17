"""Public plan detail, slots, availability, and gallery endpoints."""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import NotFoundError
from app.schemas.catalog import (
    OpenAvailabilityRead,
    PlanDurationRead,
    PlanRead,
    SlotAvailabilityRead,
    SlotRead,
)
from app.schemas.coupon import PublicOfferRead
from app.services import catalog
from app.services import coupon as coupon_service
from app.services import plan_pricing as plan_pricing_service
from app.services.slots import now_ist, today_ist

router = APIRouter(prefix="/api/v1/public", tags=["public-catalog"])


@router.get("/offers", response_model=list[PublicOfferRead])
def public_offers(db: Session = Depends(get_db)) -> list[PublicOfferRead]:
    """Active, public, currently-valid coupon offers for the home-page showcase.

    Safe fields only (code, name, description, validity). Empty list when no
    public offers exist, so the UI omits the showcase entirely.

    Uses the IST calendar date (not the server's UTC date) for the validity
    window, so an offer effective "today" in India shows from IST midnight —
    consistent with how booking dates are interpreted everywhere else.
    """
    return coupon_service.list_public_offers(db, on=now_ist().date())


class AvailableSlotsRequest(BaseModel):
    location_id: int
    booking_date: date


class OpenAvailabilityRequest(BaseModel):
    location_id: int
    booking_date: date
    duration_minutes: int


@router.get("/plans/{plan_id}", response_model=PlanRead)
def get_plan(plan_id: int, db: Session = Depends(get_db)) -> PlanRead:
    plan = catalog.get_plan(db, plan_id, today_ist())
    if plan is None:
        raise NotFoundError("Plan not found.")
    return plan


@router.get("/plans/{plan_id}/slots", response_model=list[SlotRead])
def list_slots(plan_id: int, db: Session = Depends(get_db)) -> list[SlotRead]:
    return catalog.list_active_slots(db, plan_id, today_ist())


@router.post(
    "/plans/{plan_id}/available-slots",
    response_model=list[SlotAvailabilityRead],
)
def available_slots(
    plan_id: int, body: AvailableSlotsRequest, db: Session = Depends(get_db)
) -> list[SlotAvailabilityRead]:
    """All active slots for the plan/date, each flagged with ``is_available``.

    Held (pending|accepted) slots are returned too — flagged unavailable — so
    the booking UIs can grey them out rather than hide them. The DB partial
    unique index is still the authoritative guard against double booking.
    """
    return catalog.list_slots_with_availability(
        db, plan_id, body.location_id, body.booking_date
    )


@router.get("/plans/{plan_id}/durations", response_model=list[PlanDurationRead])
def plan_durations(plan_id: int, db: Session = Depends(get_db)) -> list[PlanDurationRead]:
    """Bookable durations for a plan (open mode) with per-duration base price."""
    return [
        PlanDurationRead(
            duration_minutes=d.duration_minutes,
            price_paise=d.price_paise,
            advance_paise=d.advance_paise,
        )
        for d in plan_pricing_service.list_plan_durations(db, plan_id, today_ist())
    ]


@router.post(
    "/plans/{plan_id}/open-availability",
    response_model=list[OpenAvailabilityRead],
)
def open_availability(
    plan_id: int, body: OpenAvailabilityRequest, db: Session = Depends(get_db)
) -> list[OpenAvailabilityRead]:
    """Candidate :00/:30 start times for OPEN-mode booking of the given duration.

    Each start is flagged ``is_available`` using the public time rules and the
    overlap + cleaning-buffer check. Used by the booking UIs only when the
    location's booking_mode is 'open'; slot-mode locations use available-slots.
    """
    return catalog.generate_open_availability(
        db, plan_id, body.location_id, body.booking_date, body.duration_minutes
    )


@router.get("/plans/{plan_id}/gallery", response_model=list[str])
def plan_gallery(plan_id: int, db: Session = Depends(get_db)) -> list[str]:
    plan = catalog.get_plan(db, plan_id, today_ist())
    if plan is None:
        raise NotFoundError("Plan not found.")
    return plan.gallery_urls
