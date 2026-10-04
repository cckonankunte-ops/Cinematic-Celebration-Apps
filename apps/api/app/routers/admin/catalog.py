"""Admin catalog management endpoints (admin role only).

Create / list / update / deactivate for plans, slots, cakes, special decor, and
combos, plus plan gallery uploads. "Delete" is a soft-delete (deactivate); rows
are never hard-deleted so historical bookings keep their references.

Router-level dependencies enforce the admin role and the Origin allowlist on
writes, so every endpoint is protected by default.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import check_origin, require_role
from app.schemas.catalog_admin import (
    CakeAdminRead,
    CakeCreate,
    CakeUpdate,
    ComboAdminRead,
    ComboCreate,
    ComboUpdate,
    GalleryImageRead,
    GalleryUploadRequest,
    PlanAdminRead,
    PlanCreate,
    PlanUpdate,
    SlotAdminRead,
    SlotCreate,
    SlotUpdate,
    SpecialDecorAdminRead,
    SpecialDecorCreate,
    SpecialDecorUpdate,
)
from app.services import catalog_admin

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-catalog"],
    dependencies=[Depends(require_role("admin")), Depends(check_origin)],
)


# --- Plans ---
@router.get("/plans", response_model=list[PlanAdminRead])
def list_plans(location_id: int, db: Session = Depends(get_db)) -> list[PlanAdminRead]:
    plans = catalog_admin.list_plans_admin(db, location_id)
    return [catalog_admin.to_plan_admin_read(p) for p in plans]


@router.post("/plans", response_model=PlanAdminRead, status_code=201)
def create_plan(body: PlanCreate, db: Session = Depends(get_db)) -> PlanAdminRead:
    plan = catalog_admin.create_plan(db, body.model_dump())
    return catalog_admin.to_plan_admin_read(plan)


@router.get("/plans/{plan_id}", response_model=PlanAdminRead)
def get_plan(plan_id: int, db: Session = Depends(get_db)) -> PlanAdminRead:
    return catalog_admin.to_plan_admin_read(catalog_admin.get_plan_admin(db, plan_id))


@router.patch("/plans/{plan_id}", response_model=PlanAdminRead)
def update_plan(plan_id: int, body: PlanUpdate, db: Session = Depends(get_db)) -> PlanAdminRead:
    plan = catalog_admin.update_plan(db, plan_id, body.model_dump(exclude_unset=True))
    return catalog_admin.to_plan_admin_read(plan)


@router.delete("/plans/{plan_id}", response_model=PlanAdminRead)
def deactivate_plan(plan_id: int, db: Session = Depends(get_db)) -> PlanAdminRead:
    return catalog_admin.to_plan_admin_read(catalog_admin.deactivate_plan(db, plan_id))


# --- Plan gallery ---
@router.post("/plans/{plan_id}/gallery", response_model=GalleryImageRead, status_code=201)
def add_plan_gallery_image(
    plan_id: int, body: GalleryUploadRequest, db: Session = Depends(get_db)
) -> GalleryImageRead:
    """Return a presigned PUT URL and register the gallery row immediately."""
    upload = catalog_admin.create_gallery_upload_url(plan_id, body.filename)
    image = catalog_admin.add_gallery_image(
        db, plan_id, upload["object_key"], body.sort_order
    )
    return catalog_admin.to_gallery_image_read(image, upload_url=upload["upload_url"])


@router.delete(
    "/plans/{plan_id}/gallery/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def remove_plan_gallery_image(
    plan_id: int, image_id: int, db: Session = Depends(get_db)
) -> Response:
    catalog_admin.remove_gallery_image(db, plan_id, image_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Slots ---
@router.get("/slots", response_model=list[SlotAdminRead])
def list_slots(plan_id: int, db: Session = Depends(get_db)) -> list[SlotAdminRead]:
    slots = catalog_admin.list_slots_admin(db, plan_id)
    return [catalog_admin.to_slot_admin_read(s) for s in slots]


@router.post("/slots", response_model=SlotAdminRead, status_code=201)
def create_slot(body: SlotCreate, db: Session = Depends(get_db)) -> SlotAdminRead:
    return catalog_admin.to_slot_admin_read(catalog_admin.create_slot(db, body.model_dump()))


@router.patch("/slots/{slot_id}", response_model=SlotAdminRead)
def update_slot(slot_id: int, body: SlotUpdate, db: Session = Depends(get_db)) -> SlotAdminRead:
    slot = catalog_admin.update_slot(db, slot_id, body.model_dump(exclude_unset=True))
    return catalog_admin.to_slot_admin_read(slot)


@router.delete("/slots/{slot_id}", response_model=SlotAdminRead)
def deactivate_slot(slot_id: int, db: Session = Depends(get_db)) -> SlotAdminRead:
    return catalog_admin.to_slot_admin_read(catalog_admin.deactivate_slot(db, slot_id))


# --- Cakes ---
@router.get("/cakes", response_model=list[CakeAdminRead])
def list_cakes(location_id: int, db: Session = Depends(get_db)) -> list[CakeAdminRead]:
    cakes = catalog_admin.list_cakes_admin(db, location_id)
    return [catalog_admin.to_cake_admin_read(c) for c in cakes]


@router.post("/cakes", response_model=CakeAdminRead, status_code=201)
def create_cake(body: CakeCreate, db: Session = Depends(get_db)) -> CakeAdminRead:
    return catalog_admin.to_cake_admin_read(catalog_admin.create_cake(db, body.model_dump()))


@router.patch("/cakes/{cake_id}", response_model=CakeAdminRead)
def update_cake(cake_id: int, body: CakeUpdate, db: Session = Depends(get_db)) -> CakeAdminRead:
    cake = catalog_admin.update_cake(db, cake_id, body.model_dump(exclude_unset=True))
    return catalog_admin.to_cake_admin_read(cake)


@router.delete("/cakes/{cake_id}", response_model=CakeAdminRead)
def deactivate_cake(cake_id: int, db: Session = Depends(get_db)) -> CakeAdminRead:
    return catalog_admin.to_cake_admin_read(catalog_admin.deactivate_cake(db, cake_id))


# --- Special decor ---
@router.get("/special-decor", response_model=list[SpecialDecorAdminRead])
def list_special_decor(
    location_id: int, db: Session = Depends(get_db)
) -> list[SpecialDecorAdminRead]:
    return [
        catalog_admin.to_decor_admin_read(d)
        for d in catalog_admin.list_special_decor_admin(db, location_id)
    ]


@router.post("/special-decor", response_model=SpecialDecorAdminRead, status_code=201)
def create_special_decor(
    body: SpecialDecorCreate, db: Session = Depends(get_db)
) -> SpecialDecorAdminRead:
    decor = catalog_admin.create_special_decor(db, body.model_dump())
    return catalog_admin.to_decor_admin_read(decor)


@router.patch("/special-decor/{decor_id}", response_model=SpecialDecorAdminRead)
def update_special_decor(
    decor_id: int, body: SpecialDecorUpdate, db: Session = Depends(get_db)
) -> SpecialDecorAdminRead:
    decor = catalog_admin.update_special_decor(db, decor_id, body.model_dump(exclude_unset=True))
    return catalog_admin.to_decor_admin_read(decor)


@router.delete("/special-decor/{decor_id}", response_model=SpecialDecorAdminRead)
def deactivate_special_decor(
    decor_id: int, db: Session = Depends(get_db)
) -> SpecialDecorAdminRead:
    return catalog_admin.to_decor_admin_read(catalog_admin.deactivate_special_decor(db, decor_id))


# --- Combos ---
@router.get("/combos", response_model=list[ComboAdminRead])
def list_combos(location_id: int, db: Session = Depends(get_db)) -> list[ComboAdminRead]:
    return [
        catalog_admin.to_combo_admin_read(c)
        for c in catalog_admin.list_combos_admin(db, location_id)
    ]


@router.post("/combos", response_model=ComboAdminRead, status_code=201)
def create_combo(body: ComboCreate, db: Session = Depends(get_db)) -> ComboAdminRead:
    return catalog_admin.to_combo_admin_read(catalog_admin.create_combo(db, body.model_dump()))


@router.patch("/combos/{combo_id}", response_model=ComboAdminRead)
def update_combo(combo_id: int, body: ComboUpdate, db: Session = Depends(get_db)) -> ComboAdminRead:
    combo = catalog_admin.update_combo(db, combo_id, body.model_dump(exclude_unset=True))
    return catalog_admin.to_combo_admin_read(combo)


@router.delete("/combos/{combo_id}", response_model=ComboAdminRead)
def deactivate_combo(combo_id: int, db: Session = Depends(get_db)) -> ComboAdminRead:
    return catalog_admin.to_combo_admin_read(catalog_admin.deactivate_combo(db, combo_id))
