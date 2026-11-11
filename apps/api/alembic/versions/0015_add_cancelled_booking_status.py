"""add_cancelled_booking_status

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-11 00:00:00

Adds a ``cancelled`` value to the ``booking_status`` Postgres enum and a
``cancelled`` event type to the ``booking_events`` allowed-type CHECK.

An admin may cancel an accepted (or pending) booking at any time; this sets the
booking to ``cancelled`` (distinct from ``rejected``) and frees its slot. Only
``pending`` and ``accepted`` hold a slot, so ``cancelled`` — like ``rejected``
and ``expired`` — releases the active-slot/overlap constraint.

Postgres note: ``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction
block, so the enum change is committed on its own connection
(``connection.execution_options(isolation_level="AUTOCOMMIT")``) with
``IF NOT EXISTS`` for idempotency. Enum values cannot be dropped in Postgres, so
the downgrade leaves the ``cancelled`` value in place (documented no-op) and only
restores the narrower booking_events CHECK.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE must run outside a transaction block.
    conn = op.get_bind()
    conn.execution_options(isolation_level="AUTOCOMMIT").execute(
        _add_value_sql()
    )

    # Widen the booking_events type CHECK to include the 'cancelled' audit event.
    op.drop_constraint("ck_booking_events_type", "booking_events", type_="check")
    op.create_check_constraint(
        "ck_booking_events_type",
        "booking_events",
        "event_type IN ('created','accepted','rejected','edited',"
        "'payment_recorded','payment_voided','expired','cancelled')",
    )


def downgrade() -> None:
    # Postgres cannot drop an enum value; leave 'cancelled' in booking_status.
    op.drop_constraint("ck_booking_events_type", "booking_events", type_="check")
    op.create_check_constraint(
        "ck_booking_events_type",
        "booking_events",
        "event_type IN ('created','accepted','rejected','edited',"
        "'payment_recorded','payment_voided','expired')",
    )


def _add_value_sql():
    from sqlalchemy import text

    return text("ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'cancelled'")
