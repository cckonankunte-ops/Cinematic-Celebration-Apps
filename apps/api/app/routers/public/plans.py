"""Public plan detail, slots, availability, and gallery endpoints."""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import NotFoundError
from app.schemas.catalog import PlanRead, SlotRead
from app.services import catalog

router = APIRouter(prefix="/api/v1/public", tags=["public-catalog"])


class AvailableSlotsRequest(BaseModel):
    location_id: int
    booking_date: date


@router.get("/plans/{plan_id}", response_model=PlanRead)
def get_plan(plan_id: int, db: Session = Depends(get_db)) -> PlanRead:
    plan = catalog.get_plan(db, plan_id, date.today())
    if plan is None:
        raise NotFoundError("Plan not found.")
    return plan


@router.get("/plans/{plan_id}/slots", response_model=list[SlotRead])
def list_slots(plan_id: int, db: Session = Depends(get_db)) -> list[SlotRead]:
    return catalog.list_active_slots(db, plan_id, date.today())


@router.post("/plans/{plan_id}/available-slots", response_model=list[SlotRead])
def available_slots(
    plan_id: int, body: AvailableSlotsRequest, db: Session = Depends(get_db)
) -> list[SlotRead]:
    return catalog.list_available_slots(db, plan_id, body.location_id, body.booking_date)


@router.get("/plans/{plan_id}/gallery", response_model=list[str])
def plan_gallery(plan_id: int, db: Session = Depends(get_db)) -> list[str]:
    plan = catalog.get_plan(db, plan_id, date.today())
    if plan is None:
        raise NotFoundError("Plan not found.")
    return plan.gallery_urls
