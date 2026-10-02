"""Admin catalog write service.

Create / partial-update / deactivate for every catalog entity plus users and
plan gallery images. Catalog items and users are NEVER hard-deleted: deactivate
sets is_active = false (and effective_to = today for dated catalog rows),
preserving referential integrity for historical bookings.

Services own transactions and business rules; routers stay thin.
"""

from __future__ import annotations

import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.core.security import hash_password
from app.integrations.storage import create_upload_url, public_url
from app.models.cake import Cake
from app.models.combo_item import ComboItem
from app.models.plan import Plan, PlanGalleryImage
from app.models.slot import Slot
from app.models.special_decor_item import SpecialDecorItem
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.catalog_admin import (
    CakeAdminRead,
    ComboAdminRead,
    GalleryImageRead,
    PlanAdminRead,
    SlotAdminRead,
    SpecialDecorAdminRead,
    UserAdminRead,
)

_FAR_FUTURE = date(2099, 12, 31)


def _apply(model: object, data: dict[str, object]) -> None:
    """Set only the provided (non-None already filtered) attributes on a model."""
    for field, value in data.items():
        setattr(model, field, value)


# --- Plans ---
def create_plan(db: Session, data: dict[str, object]) -> Plan:
    """Insert a new plan and return it."""
    if data.get("effective_to") is None:
        data = {**data, "effective_to": _FAR_FUTURE}
    plan = Plan(**data)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def update_plan(db: Session, plan_id: int, data: dict[str, object]) -> Plan:
    """Partially update a plan. Raises NotFoundError if missing."""
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise NotFoundError("Plan not found.")
    _apply(plan, data)
    db.commit()
    db.refresh(plan)
    return plan


def deactivate_plan(db: Session, plan_id: int) -> Plan:
    """Soft-delete a plan (is_active=False, effective_to=today). Never hard-delete."""
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise NotFoundError("Plan not found.")
    plan.is_active = False
    plan.effective_to = date.today()
    db.commit()
    db.refresh(plan)
    return plan


def list_plans_admin(db: Session, location_id: int) -> list[Plan]:
    """All plans (active and inactive) for a location, newest list price first."""
    return list(
        db.execute(
            select(Plan).where(Plan.location_id == location_id).order_by(Plan.id)
        ).scalars()
    )


def get_plan_admin(db: Session, plan_id: int) -> Plan:
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise NotFoundError("Plan not found.")
    return plan


# --- Slots ---
def create_slot(db: Session, data: dict[str, object]) -> Slot:
    if data.get("effective_to") is None:
        data = {**data, "effective_to": _FAR_FUTURE}
    slot = Slot(**data)
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


def update_slot(db: Session, slot_id: int, data: dict[str, object]) -> Slot:
    slot = db.get(Slot, slot_id)
    if slot is None:
        raise NotFoundError("Slot not found.")
    _apply(slot, data)
    db.commit()
    db.refresh(slot)
    return slot


def deactivate_slot(db: Session, slot_id: int) -> Slot:
    slot = db.get(Slot, slot_id)
    if slot is None:
        raise NotFoundError("Slot not found.")
    slot.is_active = False
    slot.effective_to = date.today()
    db.commit()
    db.refresh(slot)
    return slot


def list_slots_admin(db: Session, plan_id: int) -> list[Slot]:
    """All slots (active and inactive) for a plan, ordered by sort_order."""
    return list(
        db.execute(
            select(Slot).where(Slot.plan_id == plan_id).order_by(Slot.sort_order, Slot.id)
        ).scalars()
    )


# --- Cakes ---
def create_cake(db: Session, data: dict[str, object]) -> Cake:
    if data.get("effective_to") is None:
        data = {**data, "effective_to": _FAR_FUTURE}
    cake = Cake(**data)
    db.add(cake)
    db.commit()
    db.refresh(cake)
    return cake


def update_cake(db: Session, cake_id: int, data: dict[str, object]) -> Cake:
    cake = db.get(Cake, cake_id)
    if cake is None:
        raise NotFoundError("Cake not found.")
    _apply(cake, data)
    db.commit()
    db.refresh(cake)
    return cake


def deactivate_cake(db: Session, cake_id: int) -> Cake:
    cake = db.get(Cake, cake_id)
    if cake is None:
        raise NotFoundError("Cake not found.")
    cake.is_active = False
    cake.effective_to = date.today()
    db.commit()
    db.refresh(cake)
    return cake


def list_cakes_admin(db: Session, location_id: int) -> list[Cake]:
    return list(
        db.execute(
            select(Cake).where(Cake.location_id == location_id).order_by(Cake.id)
        ).scalars()
    )


# --- Special decor ---
def create_special_decor(db: Session, data: dict[str, object]) -> SpecialDecorItem:
    if data.get("effective_to") is None:
        data = {**data, "effective_to": _FAR_FUTURE}
    decor = SpecialDecorItem(**data)
    db.add(decor)
    db.commit()
    db.refresh(decor)
    return decor


def update_special_decor(
    db: Session, decor_id: int, data: dict[str, object]
) -> SpecialDecorItem:
    decor = db.get(SpecialDecorItem, decor_id)
    if decor is None:
        raise NotFoundError("Special decor item not found.")
    _apply(decor, data)
    db.commit()
    db.refresh(decor)
    return decor


def deactivate_special_decor(db: Session, decor_id: int) -> SpecialDecorItem:
    decor = db.get(SpecialDecorItem, decor_id)
    if decor is None:
        raise NotFoundError("Special decor item not found.")
    decor.is_active = False
    decor.effective_to = date.today()
    db.commit()
    db.refresh(decor)
    return decor


def list_special_decor_admin(db: Session, location_id: int) -> list[SpecialDecorItem]:
    return list(
        db.execute(
            select(SpecialDecorItem)
            .where(SpecialDecorItem.location_id == location_id)
            .order_by(SpecialDecorItem.sort_order, SpecialDecorItem.id)
        ).scalars()
    )


# --- Combos ---
def create_combo(db: Session, data: dict[str, object]) -> ComboItem:
    if data.get("effective_to") is None:
        data = {**data, "effective_to": _FAR_FUTURE}
    combo = ComboItem(**data)
    db.add(combo)
    db.commit()
    db.refresh(combo)
    return combo


def update_combo(db: Session, combo_id: int, data: dict[str, object]) -> ComboItem:
    combo = db.get(ComboItem, combo_id)
    if combo is None:
        raise NotFoundError("Combo item not found.")
    _apply(combo, data)
    db.commit()
    db.refresh(combo)
    return combo


def deactivate_combo(db: Session, combo_id: int) -> ComboItem:
    combo = db.get(ComboItem, combo_id)
    if combo is None:
        raise NotFoundError("Combo item not found.")
    combo.is_active = False
    combo.effective_to = date.today()
    db.commit()
    db.refresh(combo)
    return combo


def list_combos_admin(db: Session, location_id: int) -> list[ComboItem]:
    return list(
        db.execute(
            select(ComboItem).where(ComboItem.location_id == location_id).order_by(ComboItem.id)
        ).scalars()
    )


# --- Users ---
def _role_id(db: Session, role_name: str) -> int:
    role = db.execute(
        select(UserRole).where(UserRole.name == role_name)
    ).scalar_one_or_none()
    if role is None:
        raise ValidationFailedError(f"Unknown role: {role_name}")
    return role.id


def create_user(db: Session, data: dict[str, object]) -> User:
    """Create a user: hash the password, resolve role name to role_id."""
    role_name = str(data["role"])
    user = User(
        username=str(data["username"]),
        password_hash=hash_password(str(data["password"])),
        role_id=_role_id(db, role_name),
        location_id=data.get("location_id"),  # type: ignore[arg-type]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, data: dict[str, object]) -> User:
    """Partially update a user (password re-hashed, role re-resolved if given)."""
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    if "username" in data:
        user.username = str(data["username"])
    if "password" in data:
        user.password_hash = hash_password(str(data["password"]))
    if "role" in data:
        user.role_id = _role_id(db, str(data["role"]))
    if "location_id" in data:
        user.location_id = data["location_id"]  # type: ignore[assignment]
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, user_id: int) -> User:
    """Soft-delete a user (is_active=False). Never hard-delete."""
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


def list_users_admin(db: Session) -> list[User]:
    return list(db.execute(select(User).order_by(User.id)).scalars())


def role_name(db: Session, role_id: int) -> str:
    role = db.get(UserRole, role_id)
    return role.name if role is not None else ""


# --- Plan gallery ---
def _require_plan(db: Session, plan_id: int) -> Plan:
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise NotFoundError("Plan not found.")
    return plan


def create_gallery_upload_url(plan_id: int, filename: str) -> dict[str, str]:
    """Build the public object key and a presigned PUT URL for an admin upload."""
    token = secrets.token_hex(4)
    object_key = f"plans/{plan_id}/gallery/{token}-{filename}"
    upload_url = create_upload_url(object_key)
    return {"object_key": object_key, "upload_url": upload_url}


def add_gallery_image(
    db: Session, plan_id: int, object_key: str, sort_order: int
) -> PlanGalleryImage:
    """Register a gallery image row for a plan. Raises NotFoundError if plan missing."""
    _require_plan(db, plan_id)
    image = PlanGalleryImage(plan_id=plan_id, object_key=object_key, sort_order=sort_order)
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


def remove_gallery_image(db: Session, plan_id: int, image_id: int) -> None:
    """Delete a gallery image row. Raises NotFoundError if missing."""
    image = db.execute(
        select(PlanGalleryImage).where(
            PlanGalleryImage.id == image_id, PlanGalleryImage.plan_id == plan_id
        )
    ).scalar_one_or_none()
    if image is None:
        raise NotFoundError("Gallery image not found.")
    db.delete(image)
    db.commit()


# --- Read-model mappers (admin views include is_active + validity window) ---
def to_plan_admin_read(plan: Plan) -> PlanAdminRead:
    return PlanAdminRead(
        id=plan.id,
        location_id=plan.location_id,
        title=plan.title,
        description=plan.description,
        details=plan.details,
        plan_type=plan.plan_type,
        price_paise=plan.price_paise,
        people_allowed=plan.people_allowed,
        max_people_allowed=plan.max_people_allowed,
        extra_guest_paise=plan.extra_guest_paise,
        give_discount=plan.give_discount,
        max_discount_paise=plan.max_discount_paise,
        advance_paise=plan.advance_paise,
        effective_from=plan.effective_from,
        effective_to=plan.effective_to,
        is_active=plan.is_active,
    )


def to_slot_admin_read(slot: Slot) -> SlotAdminRead:
    return SlotAdminRead(
        id=slot.id,
        plan_id=slot.plan_id,
        description=slot.description,
        show_combos=slot.show_combos,
        sort_order=slot.sort_order,
        effective_from=slot.effective_from,
        effective_to=slot.effective_to,
        is_active=slot.is_active,
    )


def to_cake_admin_read(cake: Cake) -> CakeAdminRead:
    return CakeAdminRead(
        id=cake.id,
        location_id=cake.location_id,
        description=cake.description,
        price_paise=cake.price_paise,
        object_key=cake.object_key,
        image_url=public_url(cake.object_key),
        effective_from=cake.effective_from,
        effective_to=cake.effective_to,
        is_active=cake.is_active,
    )


def to_decor_admin_read(decor: SpecialDecorItem) -> SpecialDecorAdminRead:
    return SpecialDecorAdminRead(
        id=decor.id,
        location_id=decor.location_id,
        name=decor.name,
        description=decor.description,
        price_paise=decor.price_paise,
        object_key=decor.object_key,
        image_url=public_url(decor.object_key),
        sort_order=decor.sort_order,
        effective_from=decor.effective_from,
        effective_to=decor.effective_to,
        is_active=decor.is_active,
    )


def to_combo_admin_read(combo: ComboItem) -> ComboAdminRead:
    return ComboAdminRead(
        id=combo.id,
        location_id=combo.location_id,
        name=combo.name,
        description=combo.description,
        price_paise=combo.price_paise,
        object_key=combo.object_key,
        image_url=public_url(combo.object_key),
        effective_from=combo.effective_from,
        effective_to=combo.effective_to,
        is_active=combo.is_active,
    )


def to_user_admin_read(db: Session, user: User) -> UserAdminRead:
    return UserAdminRead(
        id=user.id,
        username=user.username,
        role=role_name(db, user.role_id),
        location_id=user.location_id,
        is_active=user.is_active,
    )


def to_gallery_image_read(
    image: PlanGalleryImage, upload_url: str | None = None
) -> GalleryImageRead:
    return GalleryImageRead(
        id=image.id,
        plan_id=image.plan_id,
        object_key=image.object_key,
        image_url=public_url(image.object_key),
        sort_order=image.sort_order,
        upload_url=upload_url,
    )
