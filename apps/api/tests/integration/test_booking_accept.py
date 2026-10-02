"""Property test for accept-requires-sufficient-advance.

Feature: cinematic-celebration-system, Property 11: Accepting a pending booking
requires sufficient advance. Accept below advance raises
AcceptRequiresAdvanceError and the booking stays pending; paid >= advance
accepts; an admin may override when paid < advance; a non-admin (staff) cannot
override.

Validates: Requirements 6.4, 6.5, 7.4
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.core.errors import AcceptRequiresAdvanceError
from app.core.security import CurrentUser
from app.schemas.payment import PaymentCreate
from app.services import payments as payments_service
from app.services.booking import accept_booking
from tests.factories import make_booking, make_location, make_plan, make_slot, make_user

pytestmark = pytest.mark.integration

_ADVANCE = 50000


def _seed(db: Session, role: str) -> tuple[int, CurrentUser]:
    loc = make_location(db)
    plan = make_plan(db, loc.id, advance_paise=_ADVANCE)
    slot = make_slot(db, plan.id)
    booking = make_booking(
        db,
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        status="pending",
        advance_paise=_ADVANCE,
    )
    db.commit()
    actor_loc = None if role == "admin" else loc.id
    user = make_user(db, role, location_id=actor_loc)
    db.commit()
    actor = CurrentUser(
        id=user.id, username=user.username, role=role, location_id=actor_loc
    )
    return booking.id, actor


def _pay(db: Session, booking_id: int, amount: int, actor: CurrentUser) -> None:
    payments_service.record_payment(
        db, booking_id, PaymentCreate(method="upi", amount_paise=amount), actor
    )


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(paid=st.integers(min_value=0, max_value=_ADVANCE - 1))
def test_accept_below_advance_rejected_and_stays_pending(db: Session, paid: int) -> None:
    """Paid below advance without override keeps the booking pending."""
    booking_id, actor = _seed(db, "staff")
    if paid > 0:
        _pay(db, booking_id, paid, actor)
    with pytest.raises(AcceptRequiresAdvanceError):
        accept_booking(db, booking_id, override_advance=False, actor=actor)
    db.rollback()
    from app.models.booking import Booking

    assert db.get(Booking, booking_id).status == "pending"


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(extra=st.integers(min_value=0, max_value=100000))
def test_accept_at_or_above_advance_succeeds(db: Session, extra: int) -> None:
    """Paid >= advance accepts regardless of override."""
    booking_id, actor = _seed(db, "staff")
    _pay(db, booking_id, _ADVANCE + extra, actor)
    booking = accept_booking(db, booking_id, override_advance=False, actor=actor)
    assert booking.status == "accepted"


def test_admin_override_accepts_below_advance(db: Session) -> None:
    """An admin may override when recorded payments are below the advance."""
    booking_id, actor = _seed(db, "admin")
    booking = accept_booking(db, booking_id, override_advance=True, actor=actor)
    assert booking.status == "accepted"


def test_staff_cannot_override_below_advance(db: Session) -> None:
    """A non-admin cannot override the advance requirement."""
    booking_id, actor = _seed(db, "staff")
    with pytest.raises(AcceptRequiresAdvanceError):
        accept_booking(db, booking_id, override_advance=True, actor=actor)
