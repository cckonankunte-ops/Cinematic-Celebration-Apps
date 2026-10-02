"""Public location + per-location catalog endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.catalog import (
    CakeRead,
    ComboRead,
    LocationRead,
    OccasionRead,
    PlanRead,
    SpecialDecorRead,
)
from app.services import catalog

router = APIRouter(prefix="/api/v1/public", tags=["public-catalog"])


@router.get("/locations", response_model=list[LocationRead])
def list_locations(db: Session = Depends(get_db)) -> list[LocationRead]:
    return catalog.list_active_locations(db)


@router.get("/locations/{location_id}/plans", response_model=list[PlanRead])
def list_plans(location_id: int, db: Session = Depends(get_db)) -> list[PlanRead]:
    return catalog.list_active_plans(db, location_id, date.today())


@router.get("/locations/{location_id}/cakes", response_model=list[CakeRead])
def list_cakes(location_id: int, db: Session = Depends(get_db)) -> list[CakeRead]:
    return catalog.list_cakes(db, location_id, date.today())


@router.get(
    "/locations/{location_id}/special-decor", response_model=list[SpecialDecorRead]
)
def list_special_decor(
    location_id: int, db: Session = Depends(get_db)
) -> list[SpecialDecorRead]:
    return catalog.list_special_decor(db, location_id, date.today())


@router.get("/locations/{location_id}/combos", response_model=list[ComboRead])
def list_combos(location_id: int, db: Session = Depends(get_db)) -> list[ComboRead]:
    return catalog.list_combos(db, location_id, date.today())


@router.get("/locations/{location_id}/occasions", response_model=list[OccasionRead])
def list_occasions(location_id: int, db: Session = Depends(get_db)) -> list[OccasionRead]:
    return catalog.list_occasions(db, location_id)
