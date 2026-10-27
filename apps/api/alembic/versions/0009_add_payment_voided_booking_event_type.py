"""add_payment_voided_booking_event_type

Revision ID: 0009
Revises: 0008
Create Date: 2026-01-09 00:00:00

Adds ``payment_voided`` to the ``booking_events`` allowed-type CHECK
(``ck_booking_events_type``). Voiding a payment writes a ``payment_voided``
audit event, so the list must include it. A CHECK cannot be altered in place,
so the constraint is dropped and re-added under the same name.

Downgrade note (tightening-on-downgrade, documented precedent like 0002/0008).
The upgrade is a pure widening (adds a value to the allowed set), so it never
fails. The downgrade restores the prior list without ``payment_voided``;
re-adding the narrower CHECK **can only succeed if no ``payment_voided`` rows
exist**. Any ``payment_voided`` audit rows must be removed before the downgrade
can restore the narrower constraint.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_booking_events_type", "booking_events", type_="check")
    op.create_check_constraint(
        "ck_booking_events_type",
        "booking_events",
        "event_type IN ('created','accepted','rejected','edited',"
        "'payment_recorded','payment_voided','expired')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_booking_events_type", "booking_events", type_="check")
    # Re-adding the narrower list only succeeds if no `payment_voided` rows
    # exist (see module docstring for the rationale).
    op.create_check_constraint(
        "ck_booking_events_type",
        "booking_events",
        "event_type IN ('created','accepted','rejected','edited',"
        "'payment_recorded','expired')",
    )
