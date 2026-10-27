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

from sqlalchemy import delete, select
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
from app.core.phone import normalize_indian_mobile
from app.core.security import CurrentUser, assert_location_access
from app.integrations.payments import get_payment_provider
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.cake import Cake
from app.models.combo_item import ComboItem
from app.models.contact_lead import ContactLead
from app.models.coupon import Coupon
from app.models.coupon_redemption import CouponRedemption
from app.models.location import Location
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.slot import Slot
from app.models.special_decor_item import SpecialDecorItem
from app.schemas.booking import (
    AddonLineRead,
    AdminBookingCreate,
    AdminPreviewRequest,
    BookingCreate,
    BookingUpdate,
    ComboSelectionIn,
    ContactCreate,
    CustomerBookingResult,
    DecorSelectionIn,
    PriceBreakdownRead,
    PublicPreviewRequest,
)
from app.services import coupon as coupon_service
from app.services import payments as payments_service
from app.services.events import write_booking_event
from app.services.pricing import (
    AddonLine,
    ComboSelection,
    DecorSelection,
    PriceBreakdown,
    ValidatedCoupon,
    ValidatedRequest,
    compute_booking_price,
)

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
    special_decor: list[DecorSelectionIn],
    combos: list[ComboSelectionIn],
    cake_weight_half_kg: int = 1,
    led_name: str | None = None,
) -> ValidatedRequest:
    """Validate a booking request and return loaded, de-duplicated catalog rows.

    Raises ItemInvalidError (422 ITEM_INVALID) for unknown/invalid items (and
    for selecting more than one cake-baseline or LED-baseline combo),
    BookingDateInPastError (422) for past dates, and ValidationFailedError
    (422 VALIDATION_ERROR) when the guest count or cake weight is out of range.

    Nothing is persisted here; all checks raise before building the
    ValidatedRequest, so a failed validation leaves the session untouched.
    """
    if booking_date < _today_ist():
        raise BookingDateInPastError()

    plan = _load_valid_plan(db, location_id, plan_id, booking_date)
    _load_valid_slot(db, plan_id, slot_id, booking_date)

    if people < 1 or people > plan.max_people_allowed:
        raise ValidationFailedError(
            "The number of people exceeds the maximum allowed for this plan."
        )

    # Defensive check (the schema also enforces ge=1): cake weight is a positive
    # multiple of 0.5 kg expressed in half-kg integer units.
    if cake_weight_half_kg < 1:
        raise ValidationFailedError("Cake weight must be a positive multiple of 0.5kg.")

    cake = _load_valid_cake(db, location_id, cake_id, booking_date) if cake_id else None

    # Decor: dedupe by id (first-seen order) and SUM quantities for repeated ids.
    decor_quantities: dict[int, int] = {}
    decor_order: list[int] = []
    for sel in special_decor:
        if sel.id not in decor_quantities:
            decor_quantities[sel.id] = 0
            decor_order.append(sel.id)
        decor_quantities[sel.id] += sel.quantity
    decor_selections = [
        DecorSelection(
            item=_load_valid_decor(db, location_id, decor_id, booking_date),
            quantity=decor_quantities[decor_id],
        )
        for decor_id in decor_order
    ]

    # Combos: dedupe ids (combo quantity is always 1).
    combo_ids = _dedupe([sel.id for sel in combos])
    combo_items = [_load_valid_combo(db, location_id, c, booking_date) for c in combo_ids]

    # Multiple-baseline rule (R7.5): at most one combo may absorb the cake, and
    # at most one may absorb LED — otherwise the delta pricing is ambiguous.
    if sum(1 for c in combo_items if c.cake_baseline_paise is not None) > 1:
        raise ItemInvalidError("Only one combo may include a cake.")
    if sum(1 for c in combo_items if c.led_baseline_paise is not None) > 1:
        raise ItemInvalidError("Only one combo may include LED.")

    return ValidatedRequest(
        plan=plan,
        people=people,
        cake=cake,
        cake_weight_half_kg=cake_weight_half_kg,
        special_decor=decor_selections,
        combos=[ComboSelection(item=c) for c in combo_items],
        led_name=led_name,
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
    """Persist add-on lines, carrying quantity + cake weight snapshots.

    price_paise stores the FULL line amount (so existing readers keep working),
    while quantity/weight_half_kg are persisted for round-tripping the edit form.
    The standalone LED line (kind='led', item_id=None) is NOT persisted: the
    booking_items kind CHECK only allows cake|decor|combo, so LED text lives on
    bookings.led_name instead.
    """
    for line in lines:
        if line.kind == "led":
            continue
        db.add(
            BookingItem(
                booking_id=booking_id,
                kind=line.kind,
                item_id=line.item_id,
                name_snapshot=line.name_snapshot,
                price_paise=line.amount_paise,
                quantity=line.quantity,
                weight_half_kg=line.weight_half_kg,
            )
        )


def _resolve_coupon(
    db: Session,
    *,
    coupon_code: str | None,
    location_id: int,
    pre_coupon_total: int,
    phone: str | None,
    booking_id: int | None,
    booking_date: date | None,
) -> tuple[ValidatedCoupon | None, Coupon | None]:
    """Resolve + validate a coupon code (no writes).

    Returns (ValidatedCoupon, Coupon row) on success, or (None, None) when no
    coupon code was supplied. ``customer_key`` is the booking's Normalized_Phone
    (the phone is already validated as normalizable at the schema layer); when a
    preview carries no phone, the key is "" and simply matches no prior usage.
    Raises CouponInvalidError / CouponNotApplicableError (422) on invalid codes
    or violated usage limits.
    """
    code = (coupon_code or "").strip()
    if not code:
        return None, None

    customer_key = normalize_indian_mobile(phone or "") or ""
    coupon_row = coupon_service.resolve_coupon_row(
        db, location_id=location_id, code=code
    )
    validated = coupon_service.resolve_and_validate(
        db,
        code,
        location_id=location_id,
        pre_coupon_total=pre_coupon_total,
        customer_key=customer_key,
        booking_id=booking_id,
        on=booking_date,
    )
    return validated, coupon_row


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
        special_decor=data.special_decor,
        combos=data.combos,
        cake_weight_half_kg=data.cake_weight_half_kg,
        led_name=data.led_name,
    )
    # Two-pass coupon: price once with no coupon to get the pre-coupon total
    # (the min-order check reads it), validate the coupon against that total,
    # then re-price with the validated coupon for the final breakdown.
    pass1 = compute_booking_price(req, is_customer=True, coupon=None)
    validated, coupon_row = _resolve_coupon(
        db,
        coupon_code=data.coupon_code,
        location_id=data.location_id,
        pre_coupon_total=pass1.total_paise,
        phone=data.phone,
        booking_id=None,
        booking_date=data.booking_date,
    )
    price = compute_booking_price(req, is_customer=True, coupon=validated)

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
            led_name=data.led_name,
            people=data.people,
            occasion_id=data.occasion_id,
            plan_price_paise=price.plan_price_paise,
            extra_guest_paise=price.extra_guest_paise,
            subtotal_paise=price.subtotal_paise,
            discount_paise=price.discount_paise,
            food_paise=price.food_paise,
            other_paise=price.other_paise,
            cleaning_paise=price.cleaning_paise,
            coupon_code=price.coupon_code,
            coupon_discount_paise=price.coupon_discount_paise,
            total_paise=price.total_paise,
            advance_paise=req.plan.advance_paise,
            status="pending",
        )
        db.add(booking)
        try:
            db.flush()
            _add_booking_items(db, booking.id, price.addon_lines)
            if validated is not None and coupon_row is not None:
                coupon_service.record_redemption(
                    db,
                    coupon_row,
                    booking_id=booking.id,
                    customer_key=normalize_indian_mobile(data.phone or "") or "",
                    discount_paise=price.coupon_discount_paise,
                )
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
        special_decor=data.special_decor,
        combos=data.combos,
        cake_weight_half_kg=data.cake_weight_half_kg,
        led_name=data.led_name,
    )
    # Two-pass coupon (see create_customer_booking) with admin money fields.
    pass1 = compute_booking_price(
        req,
        discount_paise=data.discount_paise,
        food_paise=data.food_paise,
        other_paise=data.other_paise,
        cleaning_paise=data.cleaning_paise,
        is_customer=False,
        coupon=None,
    )
    validated, coupon_row = _resolve_coupon(
        db,
        coupon_code=data.coupon_code,
        location_id=data.location_id,
        pre_coupon_total=pass1.total_paise,
        phone=data.phone,
        booking_id=None,
        booking_date=data.booking_date,
    )
    price = compute_booking_price(
        req,
        discount_paise=data.discount_paise,
        food_paise=data.food_paise,
        other_paise=data.other_paise,
        cleaning_paise=data.cleaning_paise,
        is_customer=False,
        coupon=validated,
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
            led_name=data.led_name,
            people=data.people,
            occasion_id=data.occasion_id,
            plan_price_paise=price.plan_price_paise,
            extra_guest_paise=price.extra_guest_paise,
            subtotal_paise=price.subtotal_paise,
            discount_paise=price.discount_paise,
            food_paise=price.food_paise,
            other_paise=price.other_paise,
            cleaning_paise=price.cleaning_paise,
            coupon_code=price.coupon_code,
            coupon_discount_paise=price.coupon_discount_paise,
            total_paise=price.total_paise,
            advance_paise=req.plan.advance_paise,
            status="accepted",
            crm_user_id=actor.id,
        )
        db.add(booking)
        try:
            db.flush()
            _add_booking_items(db, booking.id, price.addon_lines)
            if validated is not None and coupon_row is not None:
                coupon_service.record_redemption(
                    db,
                    coupon_row,
                    booking_id=booking.id,
                    customer_key=normalize_indian_mobile(data.phone or "") or "",
                    discount_paise=price.coupon_discount_paise,
                )
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
            # Optional advance recorded at creation. Insert the ledger row +
            # audit event directly in THIS open transaction (do NOT call
            # payments_service.record_payment — it commits mid-transaction). A
            # later IntegrityError rolls this back atomically with the booking.
            # Overpayment is allowed, so there is no total check.
            if data.advance_amount_paise is not None:
                method = data.advance_method or "cash"
                db.add(
                    Payment(
                        booking_id=booking.id,
                        method=method,
                        amount_paise=data.advance_amount_paise,
                        recorded_by_user_id=actor.id,
                        provider=None,
                        provider_ref=None,
                        note="Advance recorded at booking creation",
                    )
                )
                write_booking_event(
                    db,
                    booking.id,
                    "payment_recorded",
                    actor_user_id=actor.id,
                    new_value={
                        "method": method,
                        "amount_paise": data.advance_amount_paise,
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

    # Editable-status gate (R7.6): only pending/accepted bookings may be edited.
    if booking.status not in ("pending", "accepted"):
        raise ValidationFailedError("Only pending or accepted bookings can be edited.")

    old_snapshot = _money_snapshot(booking)

    people = data.people if data.people is not None else booking.people
    discount = data.discount_paise if data.discount_paise is not None else booking.discount_paise
    food = data.food_paise if data.food_paise is not None else booking.food_paise
    other = data.other_paise if data.other_paise is not None else booking.other_paise
    cleaning = data.cleaning_paise if data.cleaning_paise is not None else booking.cleaning_paise

    # PATCH None=unchanged conventions.
    #   led_name: None -> reuse booking.led_name; "" -> clear.
    led_name = booking.led_name if data.led_name is None else data.led_name
    #   coupon_code: None -> reuse booking.coupon_code; "" -> remove the coupon.
    coupon_code = booking.coupon_code if data.coupon_code is None else data.coupon_code
    #   effective phone used for the coupon customer_key.
    effective_phone = data.phone if data.phone is not None else booking.phone

    reprice = (
        data.people is not None
        or data.cake_id is not None
        or data.special_decor is not None
        or data.combos is not None
        or data.cake_weight_half_kg is not None
        or data.led_name is not None
        or data.coupon_code is not None
        or data.discount_paise is not None
        or data.food_paise is not None
        or data.other_paise is not None
        or data.cleaning_paise is not None
    )

    if reprice:
        # Rebuild current selections from existing booking_items so omitted list
        # fields keep their current value (quantities + cake weight included).
        current_items = db.execute(
            select(BookingItem).where(BookingItem.booking_id == booking.id)
        ).scalars()
        current_cake_id: int | None = None
        current_cake_weight: int | None = None
        current_decor: list[DecorSelectionIn] = []
        current_combos: list[ComboSelectionIn] = []
        for item in current_items:
            if item.item_id is None:
                continue
            if item.kind == "cake":
                current_cake_id = item.item_id
                current_cake_weight = item.weight_half_kg
            elif item.kind == "decor":
                current_decor.append(
                    DecorSelectionIn(id=item.item_id, quantity=item.quantity)
                )
            elif item.kind == "combo":
                current_combos.append(ComboSelectionIn(id=item.item_id))

        cake_id = data.cake_id if data.cake_id is not None else current_cake_id
        special_decor = (
            data.special_decor if data.special_decor is not None else current_decor
        )
        combos = data.combos if data.combos is not None else current_combos
        # Cake weight: None -> reuse the current cake line weight (or 1).
        cake_weight_half_kg = (
            data.cake_weight_half_kg
            if data.cake_weight_half_kg is not None
            else (current_cake_weight or 1)
        )

        req = validate_booking_request(
            db,
            location_id=booking.location_id,
            plan_id=booking.plan_id,
            slot_id=booking.slot_id,
            booking_date=booking.booking_date,
            people=people,
            cake_id=cake_id,
            special_decor=special_decor,
            combos=combos,
            cake_weight_half_kg=cake_weight_half_kg,
            led_name=led_name,
        )
        # Two-pass coupon; booking_id excludes this booking's own prior redemption.
        pass1 = compute_booking_price(
            req,
            discount_paise=discount,
            food_paise=food,
            other_paise=other,
            cleaning_paise=cleaning,
            is_customer=False,
            coupon=None,
        )
        validated, coupon_row = _resolve_coupon(
            db,
            coupon_code=coupon_code,
            location_id=booking.location_id,
            pre_coupon_total=pass1.total_paise,
            phone=effective_phone,
            booking_id=booking.id,
            booking_date=booking.booking_date,
        )
        price = compute_booking_price(
            req,
            discount_paise=discount,
            food_paise=food,
            other_paise=other,
            cleaning_paise=cleaning,
            is_customer=False,
            coupon=validated,
        )
        db.execute(
            BookingItem.__table__.delete().where(BookingItem.booking_id == booking.id)
        )
        _add_booking_items(db, booking.id, price.addon_lines)

        booking.people = people
        booking.led_name = led_name
        booking.plan_price_paise = price.plan_price_paise
        booking.extra_guest_paise = price.extra_guest_paise
        booking.subtotal_paise = price.subtotal_paise
        booking.discount_paise = price.discount_paise
        booking.food_paise = price.food_paise
        booking.other_paise = price.other_paise
        booking.cleaning_paise = price.cleaning_paise
        booking.coupon_code = price.coupon_code
        booking.coupon_discount_paise = price.coupon_discount_paise
        booking.total_paise = price.total_paise

        # Keep the redemption ledger consistent with the final coupon state.
        if validated is not None and coupon_row is not None:
            coupon_service.record_redemption(
                db,
                coupon_row,
                booking_id=booking.id,
                customer_key=normalize_indian_mobile(effective_phone or "") or "",
                discount_paise=price.coupon_discount_paise,
            )
        else:
            # No coupon applies after the edit: free any prior usage.
            db.execute(
                delete(CouponRedemption).where(
                    CouponRedemption.booking_id == booking.id
                )
            )

    if data.occasion_id is not None:
        booking.occasion_id = data.occasion_id
    if data.booking_name is not None:
        booking.booking_name = data.booking_name
    if data.phone is not None:
        booking.phone = data.phone
    if data.email is not None:
        booking.email = data.email
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


def _breakdown_to_read(
    breakdown: PriceBreakdown, *, amount_paid_paise: int
) -> PriceBreakdownRead:
    """Map a pure PriceBreakdown to the API read schema with derived amounts."""
    return PriceBreakdownRead(
        plan_price_paise=breakdown.plan_price_paise,
        extra_guest_paise=breakdown.extra_guest_paise,
        addon_lines=[
            AddonLineRead(
                kind=line.kind,
                item_id=line.item_id,
                name_snapshot=line.name_snapshot,
                unit_price_paise=line.unit_price_paise,
                quantity=line.quantity,
                weight_half_kg=line.weight_half_kg,
                amount_paise=line.amount_paise,
                combo_base_paise=line.combo_base_paise,
                cake_upgrade_paise=line.cake_upgrade_paise,
                led_upgrade_paise=line.led_upgrade_paise,
            )
            for line in breakdown.addon_lines
        ],
        subtotal_paise=breakdown.subtotal_paise,
        discount_paise=breakdown.discount_paise,
        food_paise=breakdown.food_paise,
        other_paise=breakdown.other_paise,
        cleaning_paise=breakdown.cleaning_paise,
        coupon_code=breakdown.coupon_code,
        coupon_discount_paise=breakdown.coupon_discount_paise,
        total_paise=breakdown.total_paise,
        amount_paid_paise=amount_paid_paise,
        amount_due_paise=breakdown.total_paise - amount_paid_paise,
    )


def preview_booking(
    db: Session,
    data: AdminPreviewRequest | PublicPreviewRequest,
    *,
    actor: CurrentUser | None = None,
    is_customer: bool,
) -> PriceBreakdownRead:
    """Compute an authoritative price breakdown without persisting anything.

    Runs the same validation + two-pass coupon flow as the save paths but never
    writes booking_items or a redemption row. Previews carry no phone, so the
    coupon customer_key is "" (matching no prior usage); when ``booking_id`` is
    present the edited booking's own redemption is excluded from limit checks.
    """
    is_admin = isinstance(data, AdminPreviewRequest)
    if is_admin and not is_customer:
        assert_location_access(actor, data.location_id)

    req = validate_booking_request(
        db,
        location_id=data.location_id,
        plan_id=data.plan_id,
        slot_id=data.slot_id,
        booking_date=data.booking_date,
        people=data.people,
        cake_id=data.cake_id,
        special_decor=data.special_decor,
        combos=data.combos,
        cake_weight_half_kg=data.cake_weight_half_kg,
        led_name=data.led_name,
    )

    if is_admin and not is_customer:
        discount_paise = data.discount_paise
        food_paise = data.food_paise
        other_paise = data.other_paise
        cleaning_paise = data.cleaning_paise
    else:
        discount_paise = food_paise = other_paise = cleaning_paise = 0

    pass1 = compute_booking_price(
        req,
        discount_paise=discount_paise,
        food_paise=food_paise,
        other_paise=other_paise,
        cleaning_paise=cleaning_paise,
        is_customer=is_customer,
        coupon=None,
    )
    booking_id = getattr(data, "booking_id", None)
    validated, _ = _resolve_coupon(
        db,
        coupon_code=data.coupon_code,
        location_id=data.location_id,
        pre_coupon_total=pass1.total_paise,
        phone=None,  # previews carry no phone -> customer_key ""
        booking_id=booking_id,
        booking_date=data.booking_date,
    )
    price = compute_booking_price(
        req,
        discount_paise=discount_paise,
        food_paise=food_paise,
        other_paise=other_paise,
        cleaning_paise=cleaning_paise,
        is_customer=is_customer,
        coupon=validated,
    )

    # Brand-new previews have no booking, so nothing is paid yet; an edit preview
    # derives the paid amount from the existing booking's ledger.
    paid = (
        payments_service.amount_paid_paise(db, booking_id)
        if booking_id is not None
        else 0
    )
    return _breakdown_to_read(price, amount_paid_paise=paid)


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
