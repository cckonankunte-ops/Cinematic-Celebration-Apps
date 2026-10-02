"""Operational sheet services (timesheet, cakesheet).

Both reports are scoped to a location + date and ordered by ``slot.sort_order``
(then ``slot.id``) so the admin UI can group rows by time slot.

- ``timesheet`` returns ONLY accepted bookings, one row each, with the plan,
  customer, add-on names (cake / joined decor / joined combos), occasion, and
  the derived amount due.
- ``cakesheet`` returns one row per accepted booking that has a cake add-on.

Money (amount due) stays in integer paise; the UI converts to rupees.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, assert_location_access
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.occasion import Occasion
from app.models.plan import Plan
from app.models.slot import Slot
from app.schemas.sheets import CakesheetRow, TimesheetRow
from app.services import payments as payments_service


def _grouped_item_names(items: list[BookingItem]) -> dict[str, list[str]]:
    """Group add-on name snapshots by kind (cake | decor | combo)."""
    grouped: dict[str, list[str]] = {"cake": [], "decor": [], "combo": []}
    for item in items:
        grouped.setdefault(item.kind, []).append(item.name_snapshot)
    return grouped


def _accepted_bookings_by_slot(
    db: Session, location_id: int, on_date: date
) -> list[tuple[Booking, Slot]]:
    """Accepted bookings at a location+date joined to their slot, slot-ordered."""
    stmt = (
        select(Booking, Slot)
        .join(Slot, Slot.id == Booking.slot_id)
        .where(
            Booking.location_id == location_id,
            Booking.booking_date == on_date,
            Booking.status == "accepted",
        )
        .order_by(Slot.sort_order, Slot.id, Booking.id)
    )
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def timesheet(
    db: Session, actor: CurrentUser, *, location_id: int, on_date: date
) -> list[TimesheetRow]:
    """Accepted-booking operational rows for a location + date, slot-ordered."""
    assert_location_access(actor, location_id)
    rows: list[TimesheetRow] = []
    for booking, slot in _accepted_bookings_by_slot(db, location_id, on_date):
        items = list(
            db.execute(
                select(BookingItem)
                .where(BookingItem.booking_id == booking.id)
                .order_by(BookingItem.id)
            ).scalars()
        )
        grouped = _grouped_item_names(items)
        plan = db.get(Plan, booking.plan_id)
        occasion = (
            db.get(Occasion, booking.occasion_id)
            if booking.occasion_id is not None
            else None
        )
        occasion_label = booking.special_person_name
        if occasion is not None:
            occasion_label = (
                f"{occasion.name} - {booking.special_person_name}"
                if booking.special_person_name
                else occasion.name
            )
        amounts = payments_service.derive_amounts_for_booking(db, booking)
        rows.append(
            TimesheetRow(
                slot_id=slot.id,
                slot_sort_order=slot.sort_order,
                slot_description=slot.description,
                plan_title=plan.title if plan is not None else "",
                booking_name=booking.booking_name,
                phone=booking.phone,
                people=booking.people,
                name_on_cake=booking.name_on_cake,
                cake=", ".join(grouped["cake"]) or None,
                special_decor=", ".join(grouped["decor"]) or None,
                combos=", ".join(grouped["combo"]) or None,
                occasion=occasion_label,
                amount_due_paise=amounts.amount_due_paise,
            )
        )
    return rows


def cakesheet(
    db: Session, actor: CurrentUser, *, location_id: int, on_date: date
) -> list[CakesheetRow]:
    """One row per accepted booking that has a cake add-on, slot-ordered."""
    assert_location_access(actor, location_id)
    rows: list[CakesheetRow] = []
    for booking, slot in _accepted_bookings_by_slot(db, location_id, on_date):
        cakes = list(
            db.execute(
                select(BookingItem)
                .where(
                    BookingItem.booking_id == booking.id,
                    BookingItem.kind == "cake",
                )
                .order_by(BookingItem.id)
            ).scalars()
        )
        for cake in cakes:
            rows.append(
                CakesheetRow(
                    slot_id=slot.id,
                    slot_sort_order=slot.sort_order,
                    slot_description=slot.description,
                    cake=cake.name_snapshot,
                    name_on_cake=booking.name_on_cake,
                )
            )
    return rows
