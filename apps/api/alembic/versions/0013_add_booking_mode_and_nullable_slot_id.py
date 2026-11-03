"""add_booking_mode_and_nullable_slot_id

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-04 00:00:00

Per-branch booking mode (feature: booking-mode-toggle).

Additive and back-compatible:
- adds ``locations.booking_mode`` (TEXT NOT NULL, server default 'slot') with a
  CHECK constraint restricting it to 'slot' | 'open'. Every existing location
  defaults to 'slot', preserving current behaviour.
- drops NOT NULL on ``bookings.slot_id`` so 'open' mode bookings (which carry
  their window via start_time + duration_minutes and no slot row) can store
  null. The FK and its ON DELETE RESTRICT are unchanged.

No data backfill is required. The overlap exclusion constraint and the
``bookings.occupied_range`` generated column (migration 0012) are unaffected:
they key on (location, plan, date, window), not on slot_id, so open-mode
bookings with a null slot_id are enforced identically.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # locations.booking_mode: 'slot' (default) | 'open'
    op.add_column(
        "locations",
        sa.Column(
            "booking_mode",
            sa.Text(),
            nullable=False,
            server_default="slot",
        ),
    )
    op.create_check_constraint(
        "ck_locations_booking_mode",
        "locations",
        "booking_mode IN ('slot', 'open')",
    )

    # bookings.slot_id becomes nullable (open-mode bookings store null).
    op.alter_column(
        "bookings",
        "slot_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    # Re-asserting NOT NULL would fail if any open-mode (null slot_id) bookings
    # exist; this is a best-effort reverse for a clean DB.
    op.alter_column(
        "bookings",
        "slot_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.drop_constraint("ck_locations_booking_mode", "locations", type_="check")
    op.drop_column("locations", "booking_mode")
