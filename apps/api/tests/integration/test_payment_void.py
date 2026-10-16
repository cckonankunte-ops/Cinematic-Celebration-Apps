"""Payment ledger record/void integration tests (real Postgres).

Feature: admin-booking-edit, Property 28: Void inserts a reversing ledger entry.
Feature: admin-booking-edit, Property 29: Payment voiding is admin-only and
idempotent.

Payments are an append-only ledger. ``amount_paid_paise`` and the derived
``amount_due_paise`` are computed from the ledger (never stored). Voiding never
mutates/deletes the original row: it appends a negative-amount Reversing_Entry
and a single payment_voided audit event, admin-only, and each payment may be
voided at most once.

Validates: Requirements 25.4, 25.5, 25.6, 25.7, 25.8, 25.9
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.errors import (
    ForbiddenError,
    PaymentAlreadyVoidedError,
    PaymentNotVoidableError,
    ValidationFailedError,
)
from app.core.security import CurrentUser
from app.models.booking_event import BookingEvent
from app.schemas.payment import PaymentCreate
from app.services import payments as payments_service
from tests.factories import (
    make_booking,
    make_location,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration


def _admin(db: Session) -> CurrentUser:
    """Seed a real admin user so recorded_by_user_id FK resolves."""
    user = make_user(db, "admin", location_id=None)
    return CurrentUser(
        id=user.id, username=user.username, role="admin", location_id=None
    )


def _staff(db: Session, location_id: int) -> CurrentUser:
    """Seed a real staff user at the given location."""
    user = make_user(db, "staff", location_id=location_id)
    return CurrentUser(
        id=user.id, username=user.username, role="staff", location_id=location_id
    )


def _seed_booking(db: Session, *, total_paise: int = 400000):
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    booking = make_booking(
        db, location_id=loc.id, plan_id=plan.id, slot_id=slot.id,
        total_paise=total_paise,
    )
    db.commit()
    return loc, booking


def test_multiple_partial_payments_sum_and_due(db: Session) -> None:
    """Partial payments sum into amount_paid; due = total - paid."""
    _loc, booking = _seed_booking(db, total_paise=400000)
    admin = _admin(db)

    payments_service.record_payment(
        db, booking.id, PaymentCreate(method="upi", amount_paise=50000), admin
    )
    payments_service.record_payment(
        db, booking.id, PaymentCreate(method="cash", amount_paise=150000), admin
    )

    assert payments_service.amount_paid_paise(db, booking.id) == 200000
    derived = payments_service.derive_amounts_for_booking(db, booking)
    assert derived.amount_due_paise == 400000 - 200000


def test_overpayment_yields_negative_due(db: Session) -> None:
    """Recording more than the total yields a negative (overpaid) due."""
    _loc, booking = _seed_booking(db, total_paise=400000)
    admin = _admin(db)

    payments_service.record_payment(
        db, booking.id, PaymentCreate(method="cash", amount_paise=500000), admin
    )
    derived = payments_service.derive_amounts_for_booking(db, booking)
    assert derived.amount_paid_paise == 500000
    assert derived.amount_due_paise == -100000


def test_void_by_staff_forbidden_no_reversal(db: Session) -> None:
    """A staff actor cannot void: ForbiddenError and no reversing row added."""
    loc, booking = _seed_booking(db)
    admin = _admin(db)
    payment = payments_service.record_payment(
        db, booking.id, PaymentCreate(method="upi", amount_paise=50000), admin
    )
    before = payments_service.list_payments(db, booking.id)

    with pytest.raises(ForbiddenError):
        payments_service.void_payment(
            db, booking.id, payment.id, reason="mistake", actor=_staff(db, loc.id)
        )

    after = payments_service.list_payments(db, booking.id)
    assert len(after) == len(before)


def test_void_by_admin_inserts_reversal_and_audit(db: Session) -> None:
    """Admin void appends a reversal, nets the payment to zero, keeps original,
    and writes exactly one payment_voided event."""
    _loc, booking = _seed_booking(db)
    admin = _admin(db)
    payment = payments_service.record_payment(
        db, booking.id, PaymentCreate(method="upi", amount_paise=50000), admin
    )

    ledger = payments_service.void_payment(
        db, booking.id, payment.id, reason="duplicate", actor=admin
    )

    # Original + reversal both present.
    assert len(ledger) == 2
    assert any(p.id == payment.id for p in ledger)
    assert any(p.reverses_payment_id == payment.id for p in ledger)
    # Payment nets to zero.
    assert payments_service.amount_paid_paise(db, booking.id) == 0

    events = (
        db.query(BookingEvent)
        .filter(
            BookingEvent.booking_id == booking.id,
            BookingEvent.event_type == "payment_voided",
        )
        .all()
    )
    assert len(events) == 1


def test_void_same_payment_twice_rejected(db: Session) -> None:
    """Voiding a payment a second time raises PaymentAlreadyVoidedError; no add."""
    _loc, booking = _seed_booking(db)
    admin = _admin(db)
    payment = payments_service.record_payment(
        db, booking.id, PaymentCreate(method="upi", amount_paise=50000), admin
    )
    payments_service.void_payment(
        db, booking.id, payment.id, reason="duplicate", actor=admin
    )
    before = payments_service.list_payments(db, booking.id)

    with pytest.raises(PaymentAlreadyVoidedError):
        payments_service.void_payment(
            db, booking.id, payment.id, reason="again", actor=admin
        )

    after = payments_service.list_payments(db, booking.id)
    assert len(after) == len(before)


def test_void_a_reversal_row_rejected(db: Session) -> None:
    """Voiding a Reversing_Entry itself raises PaymentNotVoidableError."""
    _loc, booking = _seed_booking(db)
    admin = _admin(db)
    payment = payments_service.record_payment(
        db, booking.id, PaymentCreate(method="upi", amount_paise=50000), admin
    )
    ledger = payments_service.void_payment(
        db, booking.id, payment.id, reason="duplicate", actor=admin
    )
    reversal = next(p for p in ledger if p.reverses_payment_id == payment.id)

    with pytest.raises(PaymentNotVoidableError):
        payments_service.void_payment(
            db, booking.id, reversal.id, reason="nope", actor=admin
        )


def test_void_blank_reason_rejected_no_add(db: Session) -> None:
    """A blank reason raises ValidationFailedError and adds nothing."""
    _loc, booking = _seed_booking(db)
    admin = _admin(db)
    payment = payments_service.record_payment(
        db, booking.id, PaymentCreate(method="upi", amount_paise=50000), admin
    )
    before = payments_service.list_payments(db, booking.id)

    with pytest.raises(ValidationFailedError):
        payments_service.void_payment(
            db, booking.id, payment.id, reason="  ", actor=admin
        )

    after = payments_service.list_payments(db, booking.id)
    assert len(after) == len(before)
