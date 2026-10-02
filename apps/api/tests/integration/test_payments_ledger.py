"""Payment ledger invariant tests.

Feature: cinematic-celebration-system, Property 7: Payment ledger invariant —
derived amount due is consistent.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.core.security import CurrentUser
from app.schemas.payment import PaymentCreate
from app.services import payments
from tests.factories import make_booking, make_location, make_plan, make_slot, make_user

pytestmark = pytest.mark.integration


# --- Pure derive_amounts property (no DB) ---
@given(total=st.integers(0, 10_000_00), paid=st.integers(0, 20_000_00))
@settings(max_examples=100)
def test_derive_amounts_invariant(total: int, paid: int) -> None:
    """Property 7 (pure): due = total - paid; is_paid = paid >= total."""
    d = payments.derive_amounts(total, paid)
    assert d.amount_due_paise == total - paid
    assert d.is_paid is (paid >= total)
    # Overpayment is represented as a negative due, not clamped.
    if paid > total:
        assert d.amount_due_paise < 0


# --- DB-backed: recorded sequences increase paid by exactly the amount ---
def _seed_booking(db: Session):
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    booking = make_booking(
        db, location_id=loc.id, plan_id=plan.id, slot_id=slot.id,
        total_paise=400000, status="pending",
    )
    db.commit()
    actor = make_user(db, "admin", location_id=None)
    db.commit()
    return booking, CurrentUser(id=actor.id, username=actor.username, role="admin", location_id=None)


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(amounts=st.lists(st.integers(1, 200000), min_size=0, max_size=6))
def test_recorded_payments_sum_matches(db: Session, amounts: list[int]) -> None:
    """Property 7 (DB): paid == sum(recorded); each record adds exactly its amount.

    A fresh booking is seeded per example so Hypothesis examples are independent
    (the function-scoped db fixture is shared across examples in one call).
    """
    booking, actor = _seed_booking(db)
    running = 0
    for amt in amounts:
        payments.record_payment(db, booking.id, PaymentCreate(method="upi", amount_paise=amt), actor)
        running += amt
        assert payments.amount_paid_paise(db, booking.id) == running

    derived = payments.derive_amounts_for_booking(db, booking)
    assert derived.amount_paid_paise == sum(amounts)
    assert derived.amount_due_paise == booking.total_paise - sum(amounts)
    assert derived.is_paid is (sum(amounts) >= booking.total_paise)


def test_overpayment_reports_negative_due(db: Session) -> None:
    booking, actor = _seed_booking(db)
    payments.record_payment(
        db, booking.id, PaymentCreate(method="cash", amount_paise=500000), actor
    )
    derived = payments.derive_amounts_for_booking(db, booking)
    assert derived.is_paid is True
    assert derived.amount_due_paise == booking.total_paise - 500000
    assert derived.amount_due_paise < 0
