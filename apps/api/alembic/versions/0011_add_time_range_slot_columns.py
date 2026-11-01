"""add_time_range_slot_columns

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-30 00:00:00

Additive, nullable-first schema for time-range slots (spec: time-range-slots,
migration A). No constraints are enforced here — NOT NULL, CHECKs, and the
booking overlap exclusion constraint are added in a later migration (B) after the
backfill/verify step, so this migration is safe to run on existing data.

Adds:
- ``slots.start_time`` (TIME, null), ``slots.duration_minutes`` (SMALLINT, null)
- ``bookings.start_time`` (TIME, null), ``bookings.duration_minutes`` (SMALLINT,
  null) — snapshot of the slot time at booking creation
- ``locations.opens_at`` / ``closes_at`` / ``last_online_booking_start`` (TIME,
  defaults 10:00 / 01:00 / 22:00) and ``allow_late_booking`` (BOOL default false)
- ``plan_pricing`` table: per-(plan, duration) base price + advance
- ``btree_gist`` extension (needed by migration B's exclusion constraint)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extension for the range exclusion constraint added in migration B.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # --- slots: machine-readable time (nullable until backfilled) ---
    op.add_column("slots", sa.Column("start_time", sa.Time(), nullable=True))
    op.add_column("slots", sa.Column("duration_minutes", sa.SmallInteger(), nullable=True))

    # --- bookings: snapshot of the slot time at creation (nullable until backfilled) ---
    op.add_column("bookings", sa.Column("start_time", sa.Time(), nullable=True))
    op.add_column(
        "bookings", sa.Column("duration_minutes", sa.SmallInteger(), nullable=True)
    )

    # --- locations: working hours + online-booking policy ---
    op.add_column(
        "locations",
        sa.Column("opens_at", sa.Time(), nullable=False, server_default=sa.text("'10:00'")),
    )
    op.add_column(
        "locations",
        sa.Column("closes_at", sa.Time(), nullable=False, server_default=sa.text("'01:00'")),
    )
    op.add_column(
        "locations",
        sa.Column(
            "last_online_booking_start",
            sa.Time(),
            nullable=False,
            server_default=sa.text("'22:00'"),
        ),
    )
    op.add_column(
        "locations",
        sa.Column(
            "allow_late_booking",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # --- plan_pricing: base price + advance per (plan, duration) ---
    op.create_table(
        "plan_pricing",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.BigInteger(),
            sa.ForeignKey("plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("duration_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("price_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "advance_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "effective_to",
            sa.Date(),
            nullable=False,
            server_default=sa.text("'2099-12-31'"),
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_plan_pricing_plan_id", "plan_pricing", ["plan_id"], unique=False
    )
    # At most one active price row per (plan, duration).
    op.create_index(
        "uq_plan_pricing_active",
        "plan_pricing",
        ["plan_id", "duration_minutes"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("uq_plan_pricing_active", table_name="plan_pricing")
    op.drop_index("ix_plan_pricing_plan_id", table_name="plan_pricing")
    op.drop_table("plan_pricing")

    op.drop_column("locations", "allow_late_booking")
    op.drop_column("locations", "last_online_booking_start")
    op.drop_column("locations", "closes_at")
    op.drop_column("locations", "opens_at")

    op.drop_column("bookings", "duration_minutes")
    op.drop_column("bookings", "start_time")

    op.drop_column("slots", "duration_minutes")
    op.drop_column("slots", "start_time")

    # Leave the btree_gist extension in place (harmless; other objects may use it).
