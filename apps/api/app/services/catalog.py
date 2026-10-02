"""Catalog read service.

Read queries return only active rows whose validity window contains the
requested date. Public plan listings expose the actual chargeable price
(discount applied server-side when give_discount is true).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.storage import public_url
from app.models.cake import Cake
from app.models.combo_item import ComboItem
from app.models.location import Location
from app.models.occasion import Occasion
from app.models.plan import Plan, PlanGalleryImage
from app.models.slot import Slot
from app.models.special_decor_item import SpecialDecorItem
from app.schemas.catalog import (
    CakeRead,
    ComboRead,
    LocationRead,
    OccasionRead,
    PlanRead,
    SlotRead,
    SpecialDecorRead,
)


def chargeable_price_paise(plan: Plan) -> int:
    """Actual price a customer pays for a plan (discount applied if enabled)."""
    if plan.give_discount:
        return max(0, plan.price_paise - plan.max_discount_paise)
    return plan.price_paise


def list_active_locations(db: Session) -> list[LocationRead]:
    rows = db.execute(
        select(Location).where(Location.is_active.is_(True)).order_by(Location.name)
    ).scalars()
    return [
        LocationRead(
            id=r.id, name=r.name, slug=r.slug, address=r.address, phone=r.phone
        )
        for r in rows
    ]


def _plan_gallery_urls(db: Session, plan_id: int) -> list[str]:
    keys = db.execute(
        select(PlanGalleryImage.object_key)
        .where(PlanGalleryImage.plan_id == plan_id)
        .order_by(PlanGalleryImage.sort_order)
    ).scalars()
    return [public_url(k) for k in keys]


def _to_plan_read(db: Session, plan: Plan) -> PlanRead:
    return PlanRead(
        id=plan.id,
        location_id=plan.location_id,
        title=plan.title,
        description=plan.description,
        details=plan.details,
        plan_type=plan.plan_type,
        list_price_paise=plan.price_paise,
        price_paise=chargeable_price_paise(plan),
        people_allowed=plan.people_allowed,
        max_people_allowed=plan.max_people_allowed,
        extra_guest_paise=plan.extra_guest_paise,
        advance_paise=plan.advance_paise,
        gallery_urls=_plan_gallery_urls(db, plan.id),
    )


def list_active_plans(db: Session, location_id: int, on: date) -> list[PlanRead]:
    rows = db.execute(
        select(Plan)
        .where(
            Plan.location_id == location_id,
            Plan.is_active.is_(True),
            Plan.effective_from <= on,
            Plan.effective_to >= on,
        )
        .order_by(Plan.price_paise)
    ).scalars()
    return [_to_plan_read(db, p) for p in rows]


def get_plan(db: Session, plan_id: int, on: date) -> PlanRead | None:
    plan = db.execute(
        select(Plan).where(
            Plan.id == plan_id,
            Plan.is_active.is_(True),
            Plan.effective_from <= on,
            Plan.effective_to >= on,
        )
    ).scalar_one_or_none()
    return _to_plan_read(db, plan) if plan else None


def list_active_slots(db: Session, plan_id: int, on: date) -> list[SlotRead]:
    rows = db.execute(
        select(Slot)
        .where(
            Slot.plan_id == plan_id,
            Slot.is_active.is_(True),
            Slot.effective_from <= on,
            Slot.effective_to >= on,
        )
        .order_by(Slot.sort_order)
    ).scalars()
    return [
        SlotRead(
            id=s.id,
            plan_id=s.plan_id,
            description=s.description,
            show_combos=s.show_combos,
            sort_order=s.sort_order,
        )
        for s in rows
    ]


def list_cakes(db: Session, location_id: int, on: date) -> list[CakeRead]:
    rows = db.execute(
        select(Cake)
        .where(
            Cake.location_id == location_id,
            Cake.is_active.is_(True),
            Cake.effective_from <= on,
            Cake.effective_to >= on,
        )
        .order_by(Cake.id)
    ).scalars()
    return [
        CakeRead(
            id=c.id,
            description=c.description,
            price_paise=c.price_paise,
            image_url=public_url(c.object_key),
        )
        for c in rows
    ]


def list_special_decor(db: Session, location_id: int, on: date) -> list[SpecialDecorRead]:
    rows = db.execute(
        select(SpecialDecorItem)
        .where(
            SpecialDecorItem.location_id == location_id,
            SpecialDecorItem.is_active.is_(True),
            SpecialDecorItem.effective_from <= on,
            SpecialDecorItem.effective_to >= on,
        )
        .order_by(SpecialDecorItem.sort_order)
    ).scalars()
    return [
        SpecialDecorRead(
            id=d.id,
            name=d.name,
            description=d.description,
            price_paise=d.price_paise,
            image_url=public_url(d.object_key),
            sort_order=d.sort_order,
        )
        for d in rows
    ]


def list_combos(db: Session, location_id: int, on: date) -> list[ComboRead]:
    rows = db.execute(
        select(ComboItem)
        .where(
            ComboItem.location_id == location_id,
            ComboItem.is_active.is_(True),
            ComboItem.effective_from <= on,
            ComboItem.effective_to >= on,
        )
        .order_by(ComboItem.id)
    ).scalars()
    return [
        ComboRead(
            id=c.id,
            name=c.name,
            description=c.description,
            price_paise=c.price_paise,
            image_url=public_url(c.object_key),
        )
        for c in rows
    ]


def list_occasions(db: Session, location_id: int) -> list[OccasionRead]:
    rows = db.execute(
        select(Occasion)
        .where(Occasion.location_id == location_id, Occasion.is_active.is_(True))
        .order_by(Occasion.name)
    ).scalars()
    return [OccasionRead(id=o.id, name=o.name) for o in rows]


def list_available_slots(
    db: Session, plan_id: int, location_id: int, on: date
) -> list[SlotRead]:
    """Active slots for a plan on a date, excluding those already held.

    A slot is "held" if an active (pending|accepted) booking exists for the same
    (location, slot, date).
    """
    from app.models.booking import Booking

    held_slot_ids = set(
        db.execute(
            select(Booking.slot_id).where(
                Booking.location_id == location_id,
                Booking.booking_date == on,
                Booking.status.in_(("pending", "accepted")),
            )
        ).scalars()
    )
    return [s for s in list_active_slots(db, plan_id, on) if s.id not in held_slot_ids]


def booking_plan_and_slot_labels(
    db: Session, plan_id: int, slot_id: int
) -> tuple[str, str]:
    """Return (plan.title, slot.description) for a booking status lookup.

    Unlike the public listing queries, this ignores is_active / validity windows
    because a historical booking may reference a since-deactivated plan or slot.
    Missing rows fall back to an empty label rather than raising.
    """
    plan = db.get(Plan, plan_id)
    slot = db.get(Slot, slot_id)
    plan_title = plan.title if plan is not None else ""
    slot_description = slot.description if slot is not None else ""
    return plan_title, slot_description
