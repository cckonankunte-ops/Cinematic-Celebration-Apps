"""Catalog read service.

Read queries return only active rows whose validity window contains the
requested date. Public plan listings expose the actual chargeable price
(discount applied server-side when give_discount is true).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
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
    OpenAvailabilityRead,
    PlanRead,
    SlotAvailabilityRead,
    SlotRead,
    SpecialDecorRead,
)
from app.services.slots import (
    ActorKind,
    LocationHours,
    OccupiedWindow,
    occupied_window,
    usable_end,
    validate_booking_time,
    working_window,
)


def combo_savings_paise(price_paise: int, compare_at_paise: int | None) -> int:
    """Display-only combo saving: ``max(0, worth - price)``.

    Returns 0 when no worth is configured (``compare_at_paise is None``) or when
    the worth is at/below the charged price. Never negative, never fabricated.
    This does NOT affect what a combo is charged — it only drives the
    strike-through "Save ₹X" shown on the booking page.
    """
    if compare_at_paise is None:
        return 0
    return max(0, compare_at_paise - price_paise)


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
            id=r.id,
            name=r.name,
            slug=r.slug,
            address=r.address,
            phone=r.phone,
            map_url=r.map_url,
            opens_at=r.opens_at,
            closes_at=r.closes_at,
            last_online_booking_start=r.last_online_booking_start,
            allow_late_booking=r.allow_late_booking,
            booking_mode=r.booking_mode,
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


def _fmt_12h(t: time) -> str:
    """Format a time as e.g. '3:00 PM' (no leading zero on the hour)."""
    hour = t.hour % 12 or 12
    ampm = "AM" if t.hour < 12 else "PM"
    return f"{hour}:{t.minute:02d} {ampm}"


def slot_label(s: Slot) -> str:
    """Display label for a slot: stored description, else derived from times."""
    if s.description:
        return s.description
    if s.start_time is not None and s.duration_minutes is not None:
        end = (
            datetime.combine(date.today(), s.start_time)
            + timedelta(minutes=s.duration_minutes)
        ).time()
        return f"{_fmt_12h(s.start_time)} - {_fmt_12h(end)}"
    return ""


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
            description=slot_label(s),
            start_time=s.start_time,
            duration_minutes=s.duration_minutes,
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
            worth_paise=c.compare_at_paise,
            savings_paise=combo_savings_paise(c.price_paise, c.compare_at_paise),
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


def _active_occupied_windows(
    db: Session,
    location_id: int,
    plan_id: int,
    on: date,
    buffer_minutes: int,
    *,
    exclude_booking_id: int | None = None,
) -> list[OccupiedWindow]:
    """Occupied windows of active bookings for (location, plan, date).

    ``exclude_booking_id`` omits one booking's own window so that, when
    recomputing availability while editing that booking (e.g. shrinking its
    duration), its current window does not block the new selection.
    """
    from app.models.booking import Booking

    conds = [
        Booking.location_id == location_id,
        Booking.plan_id == plan_id,
        Booking.booking_date == on,
        Booking.status.in_(("pending", "accepted")),
        Booking.start_time.is_not(None),
        Booking.duration_minutes.is_not(None),
    ]
    if exclude_booking_id is not None:
        conds.append(Booking.id != exclude_booking_id)

    rows = db.execute(
        select(Booking.start_time, Booking.duration_minutes).where(*conds)
    ).all()
    return [
        occupied_window(on, start, duration, buffer_minutes)
        for start, duration in rows
    ]


def list_slots_with_availability(
    db: Session,
    plan_id: int,
    location_id: int,
    on: date,
    *,
    actor: ActorKind = ActorKind.PUBLIC,
    now: datetime | None = None,
    exclude_booking_id: int | None = None,
) -> list[SlotAvailabilityRead]:
    """All active slots for a plan on a date, each annotated with availability.

    Every active slot is returned (held/invalid ones flagged unavailable) so the
    booking UIs can grey them out rather than hide them. A slot is available only
    when it passes the time-rule pipeline for ``actor`` (future-start,
    working-hours, end-before-close, late-cutoff) AND its occupied window
    (incl. cleaning buffer) does not overlap any active booking's window.
    """
    buffer = settings.CLEANING_BUFFER_MINUTES
    location = db.get(Location, location_id)
    hours = (
        LocationHours(
            opens_at=location.opens_at,
            closes_at=location.closes_at,
            last_online_booking_start=location.last_online_booking_start,
            allow_late_booking=location.allow_late_booking,
        )
        if location is not None
        else None
    )
    held = _active_occupied_windows(
        db, location_id, plan_id, on, buffer, exclude_booking_id=exclude_booking_id
    )

    out: list[SlotAvailabilityRead] = []
    for s in list_active_slots(db, plan_id, on):
        available = True
        # Rule pipeline (only when the slot has real times and we know the hours).
        if s.start_time is not None and s.duration_minutes is not None and hours is not None:
            try:
                validate_booking_time(
                    hours=hours,
                    booking_date=on,
                    start=s.start_time,
                    duration_minutes=s.duration_minutes,
                    actor=actor,
                    now=now,
                )
            except AppError:
                available = False
            if available:
                window = occupied_window(on, s.start_time, s.duration_minutes, buffer)
                if any(window.overlaps(h) for h in held):
                    available = False
        out.append(
            SlotAvailabilityRead(
                id=s.id,
                plan_id=s.plan_id,
                description=s.description,
                start_time=s.start_time,
                duration_minutes=s.duration_minutes,
                show_combos=s.show_combos,
                sort_order=s.sort_order,
                is_available=available,
            )
        )
    return out


def time_range_label(start: time | None, duration_minutes: int | None) -> str:
    """Format a window as a '3:00 PM - 4:00 PM' range, or '' when unknown."""
    if start is None or duration_minutes is None:
        return ""
    end = (
        datetime.combine(date.today(), start) + timedelta(minutes=duration_minutes)
    ).time()
    return f"{_fmt_12h(start)} - {_fmt_12h(end)}"


def generate_open_availability(
    db: Session,
    plan_id: int,
    location_id: int,
    on: date,
    duration_minutes: int,
    *,
    actor: ActorKind = ActorKind.PUBLIC,
    now: datetime | None = None,
    exclude_booking_id: int | None = None,
) -> list[OpenAvailabilityRead]:
    """Candidate :00/:30 start times for OPEN-mode booking, each flagged.

    Generates starts from the location's open time up to the latest start whose
    usable end fits within the working window (midnight crossover respected),
    then flags each: available only when it passes the time-rule pipeline for
    ``actor`` AND its occupied window (incl. cleaning buffer) does not overlap an
    active booking for ``(location, plan, date)``. Buffer is never exposed.
    """
    buffer = settings.CLEANING_BUFFER_MINUTES
    location = db.get(Location, location_id)
    if location is None or duration_minutes <= 0:
        return []
    hours = LocationHours(
        opens_at=location.opens_at,
        closes_at=location.closes_at,
        last_online_booking_start=location.last_online_booking_start,
        allow_late_booking=location.allow_late_booking,
    )
    held = _active_occupied_windows(
        db, location_id, plan_id, on, buffer, exclude_booking_id=exclude_booking_id
    )
    open_dt, close_dt = working_window(on, location.opens_at, location.closes_at)

    out: list[OpenAvailabilityRead] = []
    # Step :00/:30 from open; stop once the usable end would exceed close.
    cursor = open_dt
    while usable_end(cursor.date(), cursor.time(), duration_minutes) <= close_dt:
        start = cursor.time()
        available = True
        try:
            validate_booking_time(
                hours=hours,
                booking_date=on,
                start=start,
                duration_minutes=duration_minutes,
                actor=actor,
                now=now,
            )
        except AppError:
            available = False
        if available:
            window = occupied_window(on, start, duration_minutes, buffer)
            if any(window.overlaps(h) for h in held):
                available = False
        out.append(OpenAvailabilityRead(start_time=start, is_available=available))
        cursor += timedelta(minutes=30)
    return out


def booking_plan_and_slot_labels(
    db: Session,
    plan_id: int,
    slot_id: int | None,
    *,
    start_time: time | None = None,
    duration_minutes: int | None = None,
) -> tuple[str, str]:
    """Return (plan.title, slot/window label) for a booking view.

    Slot-mode bookings (slot_id set) use the slot's stored description. Open-mode
    bookings (slot_id null) derive a time-range label from the booking's
    start_time + duration_minutes. Ignores is_active / validity so a historical
    booking referencing a since-deactivated plan/slot still labels. Missing rows
    fall back to an empty label rather than raising.
    """
    plan = db.get(Plan, plan_id)
    plan_title = plan.title if plan is not None else ""
    if slot_id is not None:
        slot = db.get(Slot, slot_id)
        slot_description = slot.description if slot is not None else ""
    else:
        slot_description = time_range_label(start_time, duration_minutes)
    return plan_title, slot_description


def booking_occasion_name(db: Session, occasion_id: int | None) -> str | None:
    """Return the occasion name for a booking, or None when unset/missing.

    Ignores is_active so a historical booking referencing a since-deactivated
    occasion still shows its label in the list view.
    """
    if occasion_id is None:
        return None
    occasion = db.get(Occasion, occasion_id)
    return occasion.name if occasion is not None else None


def location_map_url(db: Session, location_id: int) -> str | None:
    """Return the location's Google Maps share link, or None when unset."""
    location = db.get(Location, location_id)
    return location.map_url if location is not None else None
