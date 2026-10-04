"""add_plan_id_to_booking_active_slot_unique_index

Revision ID: 0002
Revises: 0001
Create Date: 2026-01-02 00:00:00

A slot is a shared time window, not a physical room; a plan is the separate
themed room. Double-booking must therefore be unique per
(location, plan, slot, date), not per (location, slot, date). This revision
widens the partial unique index ``uq_bookings_active_slot`` from the 3-column
key ``(location_id, slot_id, booking_date)`` to the 4-column key
``(location_id, plan_id, slot_id, booking_date)``, keeping the same partial
predicate ``WHERE status IN ('pending', 'accepted')`` and, critically, the same
index name so the service's constraint-name detection and the 409 mapping keep
working unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop old -> create new. This ordering is safe without a pre-check because
    # the new 4-column key is *looser* than the old 3-column key: it permits at
    # most one active row per (location, plan, slot, date), a superset of what
    # the old key (one active row per (location, slot, date)) allowed. Any data
    # that satisfied the stricter old index therefore satisfies the new one, so
    # the CREATE UNIQUE INDEX below cannot fail on existing rows.
    op.drop_index("uq_bookings_active_slot", table_name="bookings")
    op.create_index(
        "uq_bookings_active_slot",
        "bookings",
        ["location_id", "plan_id", "slot_id", "booking_date"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'accepted')"),
    )


def downgrade() -> None:
    """Restore the original 3-column active-slot unique index.

    Accepted limitation: the 3-column key is *stricter* than the 4-column key.
    If, after this revision's upgrade, different-plan rows have been inserted
    that share the same (location, slot, date) -- exactly the rows this fix
    exists to allow -- the CREATE UNIQUE INDEX below will fail with a unique
    violation, because you cannot re-impose a stricter constraint on data that
    legitimately violates it. Downgrade is therefore only safe before any such
    different-plan rows exist; otherwise the conflicting rows must be resolved
    manually first.
    """
    op.drop_index("uq_bookings_active_slot", table_name="bookings")
    op.create_index(
        "uq_bookings_active_slot",
        "bookings",
        ["location_id", "slot_id", "booking_date"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'accepted')"),
    )
