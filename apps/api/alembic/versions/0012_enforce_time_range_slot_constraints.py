"""enforce_time_range_slot_constraints

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-30 01:00:00

Migration B of the time-range-slots retrofit. Run ONLY AFTER the backfill script
(``python -m scripts.migrate_time_slots.backfill``) has populated
slots/bookings start_time + duration_minutes, resolved any unparseable slots,
and confirmed there are no existing overlapping active bookings.

Enforces:
- NOT NULL on slots/bookings ``start_time`` + ``duration_minutes``
- CHECK: slot start on the hour/half-hour; duration > 0
- a generated ``bookings.occupied_range`` (tsrange) and the overlap EXCLUSION
  constraint ``excl_bookings_active_overlap`` (the range-aware successor to
  ``uq_bookings_active_slot``), using the cleaning buffer as a literal.

Cleaning-buffer literal: the generated column expression must be immutable, so
the buffer is baked in here (seeded from the app default, 30 minutes). Changing
``CLEANING_BUFFER_MINUTES`` later requires a follow-up migration to regenerate
the column; the service-layer pre-check uses the live config value in the
meantime. (Documented trade-off from the design.)

Creating the exclusion constraint FAILS LOUDLY if any residual overlapping
active bookings exist — resolve them (see the backfill report) before migrating.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Cleaning buffer baked into the generated range (minutes). Keep in sync with
# CLEANING_BUFFER_MINUTES; changing it needs a new migration (see docstring).
_BUFFER_MINUTES = 30


def upgrade() -> None:
    # --- NOT NULL (data backfilled by the retrofit script) ---
    op.alter_column("slots", "start_time", nullable=False)
    op.alter_column("slots", "duration_minutes", nullable=False)
    op.alter_column("bookings", "start_time", nullable=False)
    op.alter_column("bookings", "duration_minutes", nullable=False)

    # --- CHECK constraints ---
    op.create_check_constraint(
        "ck_slots_start_half_hour",
        "slots",
        "EXTRACT(MINUTE FROM start_time) IN (0,30) "
        "AND EXTRACT(SECOND FROM start_time) = 0",
    )
    op.create_check_constraint(
        "ck_slots_duration_positive", "slots", "duration_minutes > 0"
    )
    op.create_check_constraint(
        "ck_bookings_duration_positive", "bookings", "duration_minutes > 0"
    )

    # --- Generated occupied_range + overlap exclusion constraint ---
    # anchor = booking_date + start_time; end = anchor + (duration + buffer) min.
    # Anchoring on a timestamp makes midnight crossover automatic. Half-open [)
    # so back-to-back bookings at the buffer boundary do not overlap.
    op.execute(
        f"""
        ALTER TABLE bookings
        ADD COLUMN occupied_range tsrange
        GENERATED ALWAYS AS (
            tsrange(
                (booking_date + start_time),
                (booking_date + start_time)
                    + make_interval(mins => duration_minutes + {_BUFFER_MINUTES}),
                '[)'
            )
        ) STORED
        """
    )

    # Drop the old equality-based double-booking guard, replaced by the range one.
    op.drop_index("uq_bookings_active_slot", table_name="bookings")

    # Range exclusion: no two active bookings for the same (location, plan) may
    # have overlapping occupied ranges. btree_gist (created in 0011) enables the
    # equality part on location_id/plan_id.
    op.execute(
        """
        ALTER TABLE bookings
        ADD CONSTRAINT excl_bookings_active_overlap
        EXCLUDE USING gist (
            location_id WITH =,
            plan_id WITH =,
            occupied_range WITH &&
        ) WHERE (status IN ('pending','accepted'))
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP CONSTRAINT excl_bookings_active_overlap")
    op.execute("ALTER TABLE bookings DROP COLUMN occupied_range")

    # Restore the original partial unique index (one active per loc/plan/slot/date).
    op.execute(
        """
        CREATE UNIQUE INDEX uq_bookings_active_slot
        ON bookings (location_id, plan_id, slot_id, booking_date)
        WHERE status IN ('pending','accepted')
        """
    )

    op.drop_constraint("ck_bookings_duration_positive", "bookings", type_="check")
    op.drop_constraint("ck_slots_duration_positive", "slots", type_="check")
    op.drop_constraint("ck_slots_start_half_hour", "slots", type_="check")

    op.alter_column("bookings", "duration_minutes", nullable=True)
    op.alter_column("bookings", "start_time", nullable=True)
    op.alter_column("slots", "duration_minutes", nullable=True)
    op.alter_column("slots", "start_time", nullable=True)
