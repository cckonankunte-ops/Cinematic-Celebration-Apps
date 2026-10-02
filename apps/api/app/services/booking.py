"""Booking validation and creation service.

Owns booking transactions. Validation loads and verifies every catalog ID
against the location and booking date; pricing is delegated to the pure
``services.pricing`` module. Double-booking is prevented by the DB partial
unique index ``uq_bookings_active_slot``; on that violation we raise
``SlotUnavailableError``. On a ``booking_reference`` collision we regenerate the
reference and retry.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import (
    AcceptRequiresAdvanceError,
    BookingDateInPastError,
    ItemInvalidError,
    NotFoundError,
    SlotUnavailableError,
    ValidationFailedError,
)
from app.core.security import CurrentUser, assert_location_access
from app.integrations.payments import get_payment_provider
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.cake import Cake
from app.models.combo_item import ComboItem
from app.models.contact_lead import ContactLead
from app.models.location import Location
from app.models.plan import Plan
from app.models.slot import Slot
from app.models.special_decor_item import SpecialDecorItem
from app.schemas.booking import (
    AdminBookingCreate,
    BookingCreate,
    BookingUpdate,
    ContactCreate,
    CustomerBookingResult,
)
from app.services import payments as payments_service
from app.services.events import write_booking_event
from app.services.pricing import AddonLine, ValidatedRequest, compute_booking_price

_IST = ZoneInfo("Asia/Kolkata")
_MAX_REFERENCE_ATTEMPTS = 5


def _today_ist() -> date:
    """Return today's date in Asia/Kolkata (booking dates are IST)."""
    return datetime.now(_IST).date()


def _dedupe(ids: list[int]) -> list[int]:
    """Remove duplicate IDs while preserving first-seen order."""
    seen: set[int] = set()
    out: list[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _load_valid_plan(db: Session, location_id: int, plan_id: int, on: date) -> Plan:
    plan = db.get(Plan, plan_id)
    if (
        plan is None
        or plan.location_id != location_id
        or not plan.is_active
        or not (plan.effective_from <= on <= plan.effective_to)
    ):
        raise ItemInvalidError("The selected plan is not valid for this location or date.")
    return plan


def _load_valid_slot(db: Session, plan_id: int, slot_id: int, on: date) -> Slot:
    slot = db.get(Slot, slot_id)
    if (
        slot is None
        or slot.plan_id != plan_id
        or not slot.is_active
        or not (slot.effective_from <= on <= slot.effective_to)
    ):
        raise ItemInvalidError("The selected slot is not valid for this plan or date.")
    return slot


def _load_valid_cake(db: Session, location_id: int, cake_id: int, on: date) -> Cake:
    cake = db.get(Cake, cake_id)
    if (
        cake is None
        or cake.location_id != location_id
        or not cake.is_active
        or not (cake.effective_from <= on <= cake.effective_to)
    ):
        raise ItemInvalidError("The selected cake is not valid for this location or date.")
    return cake


def _load_valid_decor(
    db: Session, location_id: int, decor_id: int, on: date
) -> SpecialDecorItem:
    decor = db.get(SpecialDecorItem, decor_id)
    if (
        decor is None
        or decor.location_id != location_id
        or not decor.is_active
        or not (decor.effective_from <= on <= decor.effective_to)
    ):
        raise ItemInvalidError("A selected decor item is not valid for this location or date.")
    return decor


def _load_valid_combo(db: Session, location_id: int, combo_id: int, on: date) -> ComboItem:
    combo = db.get(ComboItem, combo_id)
    if (
        combo is None
        or combo.location_id != location_id
        or not combo.is_active
        or not (combo.effective_from <= on <= combo.effective_to)
    ):
        raise ItemInvalidError("A selected combo is not valid for this location or date.")
    return combo


def validate_booking_request(
    db: Session,
    *,
    location_id: int,
    plan_id: int,
    slot_id: int,
    booking_date: date,
    people: int,
    cake_id: int | None,
    special_decor_ids: list[int],
    combo_ids: list[int],
) -> ValidatedRequest:
    """Validate a booking request and return loaded, de-duplicated catalog rows.

    Raises ItemInvalidError (422 ITEM_INVALID) for unknown/invalid items,
    BookingDateInPastError (422) for past dates, and ValidationFailedError
    (422 VALIDATION_ERROR) when the guest count is out of range.
    """
    if booking_date < _today_ist():
        raise BookingDateInPastError()

    plan = _load_valid_plan(db, location_id, plan_id, booking_date)
    _load_valid_slot(db, plan_id, slot_id, booking_date)

    if people < 1 or people > plan.max_people_allowed:
        raise ValidationFailedError(
            "The number of people exceeds the maximum allowed for this plan."
        )

    cake = _load_valid_cake(db, location_id, cake_id, booking_date) if cake_id else None

    decor_ids = _dedupe(special_decor_ids)
    combo_id_list = _dedupe(combo_ids)
    decor = [_load_valid_decor(db, location_id, d, booking_date) for d in decor_ids]
    combos = [_load_valid_combo(db, location_id, c, booking_date) for c in combo_id_list]

    return ValidatedRequest(
        plan=plan,
        people=people,
        cake=cake,
        special_decor=decor,
        combos=combos,
    )


def generate_reference(location: Location, booking_date: date) -> str:
    """Build a human-friendly booking reference: CC-{ABBREV}-{YYYYMMDD}-{HEX}."""
    source = location.slug or location.name
    abbrev = "".join(ch for ch in source if ch.isalnum())[:3].upper() or "LOC"
    hex_part = secrets.token_hex(2).upper()
    return f"CC-{abbrev}-{booking_date.strftime('%Y%m%d')}-{hex_part}"


@dataclass(frozen=True)
class _ConstraintCheck:
    is_slot_conflict: bool
    is_reference_conflict: bool


def _classify_integrity_error(exc: IntegrityError) -> _ConstraintCheck:
    detail = str(getattr(exc, "orig", exc))
    return _ConstraintCheck(
        is_slot_conflict="uq_bookings_active_slot" in detail,
        is_reference_conflict="booking_reference" in detail,
    )


def _add_booking_items(db: Session, booking_id: int, lines: list[AddonLine]) -> None:
    for line in lines:
        db.add(
            BookingItem(
                booking_id=booking_id,
                kind=line.kind,
                item_id=line.item_id,
                name_snapshot=line.name_snapshot,
                price_paise=line.price_paise,
            )
        )


def create_customer_booking(db: Session, data: BookingCreate) -> CustomerBookingResult:
    """Create a pending customer booking request in a single transaction.

    Validates the request, computes the authoritative price (customer discount
    forced to 0), inserts the booking + add-on items + a 'created' audit event,
    then returns payment instructions from the payment provider. On a slot
    conflict raises SlotUnavailableError; on a reference collision retries with
    a fresh reference.
    """
    req = validate_booking_request(
        db,
        location_id=data.location_id,
        plan_id=data.plan_id,
        slot_id=data.slot_id,
        booking_date=data.booking_date,
        people=data.people,
        cake_id=data.cake_id,
        special_decor_ids=data.special_decor_ids,
        combo_ids=data.combo_ids,
    )
    price = compute_booking_price(req, is_customer=True)

    location = db.get(Location, data.location_id)
    if location is None:
        raise ItemInvalidError("The selected location is not valid.")

    public_token = secrets.token_urlsafe(12)
    advance_paise = req.plan.advance_paise
    final_reference = ""

    for _ in range(_MAX_REFERENCE_ATTEMPTS):
        booking_reference = generate_reference(location, data.booking_date)
        booking = Booking(
            booking_reference=booking_reference,
            public_token=public_token,
            location_id=data.location_id,
            plan_id=data.plan_id,
            slot_id=data.slot_id,
            booking_date=data.booking_date,
            booking_name=data.booking_name,
            email=data.email,
            phone=data.phone,
            special_person_name=data.special_person_name,
            name_on_cake=data.name_on_cake,
            message=data.message,
            people=data.people,
            occasion_id=data.occasion_id,
            plan_price_paise=price.plan_price_paise,
            extra_guest_paise=price.extra_guest_paise,
            subtotal_paise=price.subtotal_paise,
            discount_paise=price.discount_paise,
            food_paise=price.food_paise,
            other_paise=price.other_paise,
            cleaning_paise=price.cleaning_paise,
            total_paise=price.total_paise,
            advance_paise=req.plan.advance_paise,
            status="pending",
        )
        db.add(booking)
        try:
            db.flush()
            _add_booking_items(db, booking.id, price.addon_lines)
            write_booking_event(
                db,
                booking.id,
                "created",
                new_value={
                    "status": "pending",
                    "total_paise": price.total_paise,
                    "people": data.people,
                },
            )
            final_reference = booking_reference
            db.commit()
            break
        except IntegrityError as exc:
            db.rollback()
            check = _classify_integrity_error(exc)
            if check.is_slot_conflict:
                raise SlotUnavailableError() from exc
            if check.is_reference_conflict:
                continue  # regenerate reference and retry
            raise
    else:  # pragma: no cover - exhausting 5 unique references is astronomically unlikely
        raise ItemInvalidError("Could not allocate a unique booking reference.")

    instructions = get_payment_provider().create_order(final_reference, advance_paise)
    return CustomerBookingResult(
        booking_token=public_token,
        advance_paise=advance_paise,
        payment_instructions=instructions,
    )


def get_booking_by_token(db: Session, public_token: str) -> Booking:
    """Return a booking by its public token, or raise NotFoundError."""
    booking = db.execute(
        select(Booking).where(Booking.public_token == public_token)
    ).scalar_one_or_none()
    if booking is None:
        raise NotFoundError("Booking not found.")
    return booking


def create_contact_lead(db: Session, data: ContactCreate) -> ContactLead:
    """Persist a public contact-form submission."""
    lead = ContactLead(
        name=data.name,
        phone=data.phone,
        email=data.email,
        message=data.message,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _money_snapshot(booking: Booking) -> dict:
    """Capture the booking's status + money fields for an audit event value."""
    return {
        "status": booking.status,
        "people": booking.people,
        "subtotal_paise": booking.subtotal_paise,
        "discount_paise": booking.discount_paise,
        "food_paise": booking.food_paise,
        "other_paise": booking.other_paise,
        "cleaning_paise": booking.cleaning_paise,
        "total_paise": booking.total_paise,
    }


def create_admin_booking(
    db: Session, data: AdminBookingCreate, actor: CurrentUser
) -> Booking:
    """Create an admin booking (status='accepted') in a single transaction.

    Validates the request, computes the authoritative price with admin discount,
    inserts the booking + add-on items + a 'created' audit event. No payment
    provider call. Slot conflicts raise SlotUnavailableError; reference
    collisions regenerate and retry.
    """
    assert_location_access(actor, data.location_id)
    req = validate_booking_request(
        db,
        location_id=data.location_id,
        plan_id=data.plan_id,
        slot_id=data.slot_id,
        booking_date=data.booking_date,
        people=data.people,
        cake_id=data.cake_id,
        special_decor_ids=data.special_decor_ids,
        combo_ids=data.combo_ids,
    )
    price = compute_booking_price(
        req,
        discount_paise=data.discount_paise,
        food_paise=data.food_paise,
        other_paise=data.other_paise,
        cleaning_paise=data.cleaning_paise,
        is_customer=False,
    )

    location = db.get(Location, data.location_id)
    if location is None:
        raise ItemInvalidError("The selected location is not valid.")

    public_token = secrets.token_urlsafe(12)

    for _ in range(_MAX_REFERENCE_ATTEMPTS):
        booking = Booking(
            booking_reference=generate_reference(location, data.booking_date),
            public_token=public_token,
            location_id=data.location_id,
            plan_id=data.plan_id,
            slot_id=data.slot_id,
            booking_date=data.booking_date,
            booking_name=data.booking_name,
            email=data.email,
            phone=data.phone,
            special_person_name=data.special_person_name,
            name_on_cake=data.name_on_cake,
            message=data.message,
            people=data.people,
            occasion_id=data.occasion_id,
            plan_price_paise=price.plan_price_paise,
            extra_guest_paise=price.extra_guest_paise,
            subtotal_paise=price.subtotal_paise,
            discount_paise=price.discount_paise,
            food_paise=price.food_paise,
            other_paise=price.other_paise,
            cleaning_paise=price.cleaning_paise,
            total_paise=price.total_paise,
            advance_paise=req.plan.advance_paise,
            status="accepted",
            crm_user_id=actor.id,
        )
        db.add(booking)
        try:
            db.flush()
            _add_booking_items(db, booking.id, price.addon_lines)
            write_booking_event(
                db,
                booking.id,
                "created",
                actor_user_id=actor.id,
                new_value={
                    "status": "accepted",
                    "total_paise": price.total_paise,
                    "people": data.people,
                },
            )
            db.commit()
            db.refresh(booking)
            return booking
        except IntegrityError as exc:
            db.rollback()
            check = _classify_integrity_error(exc)
            if check.is_slot_conflict:
                raise SlotUnavailableError() from exc
            if check.is_reference_conflict:
                continue  # regenerate reference and retry
            raise
    # pragma: no cover - exhausting 5 unique references is astronomically unlikely
    raise ItemInvalidError("Could not allocate a unique booking reference.")


def _load_booking_for_actor(db: Session, booking_id: int, actor: CurrentUser) -> Booking:
    """Load a booking (NotFound if missing) and enforce location access."""
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found.")
    assert_location_access(actor, booking.location_id)
    return booking


def update_booking(
    db: Session, booking_id: int, data: BookingUpdate, actor: CurrentUser
) -> Booking:
    """Edit a booking: re-validate + re-price when items/people change.

    Captures an old snapshot, applies scalar updates, replaces booking_items
    when the priced inputs change, and writes an 'edited' audit event, all in a
    single transaction.
    """
    booking = _load_booking_for_actor(db, booking_id, actor)
    old_snapshot = _money_snapshot(booking)

    people = data.people if data.people is not None else booking.people
    discount = data.discount_paise if data.discount_paise is not None else booking.discount_paise
    food = data.food_paise if data.food_paise is not None else booking.food_paise
    other = data.other_paise if data.other_paise is not None else booking.other_paise
    cleaning = data.cleaning_paise if data.cleaning_paise is not None else booking.cleaning_paise

    reprice = (
        data.people is not None
        or data.cake_id is not None
        or data.special_decor_ids is not None
        or data.combo_ids is not None
        or data.discount_paise is not None
        or data.food_paise is not None
        or data.other_paise is not None
        or data.cleaning_paise is not None
    )

    if reprice:
        current_items = db.execute(
            select(BookingItem).where(BookingItem.booking_id == booking.id)
        ).scalars()
        current_cake_id: int | None = None
        current_decor_ids: list[int] = []
        current_combo_ids: list[int] = []
        for item in current_items:
            if item.item_id is None:
                continue
            if item.kind == "cake":
                current_cake_id = item.item_id
            elif item.kind == "decor":
                current_decor_ids.append(item.item_id)
            elif item.kind == "combo":
                current_combo_ids.append(item.item_id)

        cake_id = data.cake_id if data.cake_id is not None else current_cake_id
        decor_ids = (
            data.special_decor_ids if data.special_decor_ids is not None else current_decor_ids
        )
        combo_ids = data.combo_ids if data.combo_ids is not None else current_combo_ids

        req = validate_booking_request(
            db,
            location_id=booking.location_id,
            plan_id=booking.plan_id,
            slot_id=booking.slot_id,
            booking_date=booking.booking_date,
            people=people,
            cake_id=cake_id,
            special_decor_ids=decor_ids,
            combo_ids=combo_ids,
        )
        price = compute_booking_price(
            req,
            discount_paise=discount,
            food_paise=food,
            other_paise=other,
            cleaning_paise=cleaning,
            is_customer=False,
        )
        db.execute(
            BookingItem.__table__.delete().where(BookingItem.booking_id == booking.id)
        )
        _add_booking_items(db, booking.id, price.addon_lines)

        booking.people = people
        booking.plan_price_paise = price.plan_price_paise
        booking.extra_guest_paise = price.extra_guest_paise
        booking.subtotal_paise = price.subtotal_paise
        booking.discount_paise = price.discount_paise
        booking.food_paise = price.food_paise
        booking.other_paise = price.other_paise
        booking.cleaning_paise = price.cleaning_paise
        booking.total_paise = price.total_paise

    if data.occasion_id is not None:
        booking.occasion_id = data.occasion_id
    if data.booking_name is not None:
        booking.booking_name = data.booking_name
    if data.phone is not None:
        booking.phone = data.phone
    if data.special_person_name is not None:
        booking.special_person_name = data.special_person_name
    if data.name_on_cake is not None:
        booking.name_on_cake = data.name_on_cake
    if data.message is not None:
        booking.message = data.message

    write_booking_event(
        db,
        booking.id,
        "edited",
        actor_user_id=actor.id,
        old_value=old_snapshot,
        new_value=_money_snapshot(booking),
    )
    db.commit()
    db.refresh(booking)
    return booking


def accept_booking(
    db: Session, booking_id: int, *, override_advance: bool, actor: CurrentUser
) -> Booking:
    """Accept a pending booking; requires recorded advance unless admin override.

    The confirmation email is scheduled by the router via BackgroundTasks after
    this returns; the service only updates state and writes the audit event.
    """
    booking = _load_booking_for_actor(db, booking_id, actor)
    if booking.status != "pending":
        raise ValidationFailedError("Only pending bookings can be accepted.")

    paid = payments_service.amount_paid_paise(db, booking_id)
    if paid < booking.advance_paise and not (override_advance and actor.role == "admin"):
        raise AcceptRequiresAdvanceError()

    old_snapshot = {"status": booking.status}
    booking.status = "accepted"
    write_booking_event(
        db,
        booking.id,
        "accepted",
        actor_user_id=actor.id,
        old_value=old_snapshot,
        new_value={"status": "accepted"},
    )
    db.commit()
    db.refresh(booking)
    return booking


def reject_booking(db: Session, booking_id: int, *, actor: CurrentUser) -> Booking:
    """Reject a booking and write a 'rejected' audit event."""
    booking = _load_booking_for_actor(db, booking_id, actor)
    old_snapshot = {"status": booking.status}
    booking.status = "rejected"
    write_booking_event(
        db,
        booking.id,
        "rejected",
        actor_user_id=actor.id,
        old_value=old_snapshot,
        new_value={"status": "rejected"},
    )
    db.commit()
    db.refresh(booking)
    return booking


def list_booking_items(db: Session, booking_id: int) -> list[BookingItem]:
    """Return the add-on line items for a booking, oldest first."""
    return list(
        db.execute(
            select(BookingItem)
            .where(BookingItem.booking_id == booking_id)
            .order_by(BookingItem.id)
        ).scalars()
    )


def get_booking(db: Session, booking_id: int, actor: CurrentUser) -> Booking:
    """Load a single booking enforcing location access (NotFound if missing)."""
    return _load_booking_for_actor(db, booking_id, actor)


def list_bookings(
    db: Session,
    actor: CurrentUser,
    *,
    location_id: int,
    on: date | None = None,
    status: str | None = None,
) -> list[Booking]:
    """List bookings for a location, ordered by slot sort_order then slot id.

    Staff are restricted to their location. Rejected bookings are excluded
    unless a status filter is given explicitly.
    """
    assert_location_access(actor, location_id)
    stmt = (
        select(Booking)
        .join(Slot, Slot.id == Booking.slot_id)
        .where(Booking.location_id == location_id)
    )
    if on is not None:
        stmt = stmt.where(Booking.booking_date == on)
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    else:
        stmt = stmt.where(Booking.status != "rejected")
    stmt = stmt.order_by(Slot.sort_order, Slot.id, Booking.id)
    return list(db.execute(stmt).scalars())


def expire_cutoff(now: datetime) -> datetime:
    """Return the created_at cutoff: pending bookings older than this expire."""
    return now - timedelta(minutes=settings.PENDING_HOLD_MINUTES)


def expire_pending_bookings(db: Session) -> int:
    """Expire pending bookings older than PENDING_HOLD_MINUTES (idempotent).

    In one transaction, selects pending bookings created before the cutoff, sets
    them to 'expired', and writes one 'expired' audit event each. Returns the
    number of bookings expired. No payment columns are involved.
    """
    cutoff = expire_cutoff(datetime.now(tz=UTC))
    bookings = list(
        db.execute(
            select(Booking).where(
                Booking.status == "pending", Booking.created_at < cutoff
            )
        ).scalars()
    )
    for booking in bookings:
        booking.status = "expired"
        write_booking_event(
            db,
            booking.id,
            "expired",
            old_value={"status": "pending"},
            new_value={"status": "expired"},
        )
    db.commit()
    return len(bookings)
