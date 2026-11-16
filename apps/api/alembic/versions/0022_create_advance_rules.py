"""create_advance_rules

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-16 00:00:00

Threshold-based advance rules per branch (feature: customer-booking-flow-v2).

Creates ``advance_rules``: per-location (min_total_paise -> advance_paise) pairs.
Pricing selects the highest ``min_total_paise`` the booking's FINAL total meets;
when no rule matches it falls back to the plan's ``advance_paise``. A unique
index on ``(location_id, min_total_paise)`` keeps thresholds distinct per branch
so exactly one rule can win. Both money columns have a non-negative CHECK. FK to
locations is ON DELETE CASCADE.

``downgrade()`` drops the table (index first).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "advance_rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("min_total_paise", sa.BigInteger(), nullable=False),
        sa.Column("advance_paise", sa.BigInteger(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_advance_rules"),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_advance_rules_location_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "min_total_paise >= 0", name="ck_advance_rules_min_total_nonneg"
        ),
        sa.CheckConstraint(
            "advance_paise >= 0", name="ck_advance_rules_advance_nonneg"
        ),
        sa.UniqueConstraint(
            "location_id",
            "min_total_paise",
            name="uq_advance_rules_location_threshold",
        ),
    )
    op.create_index(
        "ix_advance_rules_location_id",
        "advance_rules",
        ["location_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_advance_rules_location_id", table_name="advance_rules")
    op.drop_table("advance_rules")
