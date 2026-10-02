"""Admin user management endpoints (admin role only).

Create / list / update / deactivate staff and admin users. Users are never
hard-deleted (deactivate sets is_active=False) so historical crm/recorded_by
references survive. Password hashes are never returned.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import check_origin, require_role
from app.schemas.catalog_admin import UserAdminRead, UserCreate, UserUpdate
from app.services import catalog_admin

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-users"],
    dependencies=[Depends(require_role("admin")), Depends(check_origin)],
)


@router.get("/users", response_model=list[UserAdminRead])
def list_users(db: Session = Depends(get_db)) -> list[UserAdminRead]:
    return [catalog_admin.to_user_admin_read(db, u) for u in catalog_admin.list_users_admin(db)]


@router.post("/users", response_model=UserAdminRead, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db)) -> UserAdminRead:
    user = catalog_admin.create_user(db, body.model_dump())
    return catalog_admin.to_user_admin_read(db, user)


@router.patch("/users/{user_id}", response_model=UserAdminRead)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db)) -> UserAdminRead:
    user = catalog_admin.update_user(db, user_id, body.model_dump(exclude_unset=True))
    return catalog_admin.to_user_admin_read(db, user)


@router.delete("/users/{user_id}", response_model=UserAdminRead)
def deactivate_user(user_id: int, db: Session = Depends(get_db)) -> UserAdminRead:
    return catalog_admin.to_user_admin_read(db, catalog_admin.deactivate_user(db, user_id))
