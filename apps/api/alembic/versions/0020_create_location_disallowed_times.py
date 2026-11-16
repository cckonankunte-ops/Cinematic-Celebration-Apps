"""create_location_disallowed_times

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-16 00:00:00

Admin-configurable disallowed booking times per branch (feature:
customer-booking-flow-v2).

Creates ``location_disallowed_times`` — one row per blocked wall-clock (IST)
range for a location. ``max_duration_minutes`` NULL blocks any overlapping
booking; when set, only bookings of that duration or shorter are blocked. A
CHECK enforces ``start_time < end_time``. FK to locations is ON DELETE CASCADE.
Config is forward-looking: enforced only at availability/creation time.

``downgrade()`` drops the table (index first).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "location_disallowed_times",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("max_duration_minutes", sa.SmallInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        sa.PrimaryKeyConstraint("id", name="pk_location_disallowed_times"),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_location_disallowed_times_location_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "start_time < end_time", name="ck_location_disallowed_times_order"
        ),
    )
    op.create_index(
        "ix_location_disallowed_times_location_id",
        "location_disallowed_times",
        ["location_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_location_disallowed_times_location_id",
        table_name="location_disallowed_times",
    )
    op.drop_table("location_disallowed_times")
