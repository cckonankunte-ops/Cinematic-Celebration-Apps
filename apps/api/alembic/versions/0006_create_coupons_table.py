"""create_coupons_table

Revision ID: 0006
Revises: 0005
Create Date: 2026-01-06 00:00:00

Creates the ``coupons`` table: location-scoped, admin-managed flat or
percentage discounts with an optional cap, a configurable percentage base, and
selectable usage limits.

- ``value`` holds paise for ``flat`` coupons and an integer percent (0-100) for
  ``percentage`` coupons. The DB enforces only ``value >= 0``; the percentage
  upper bound (``<= 100``) is type-dependent and enforced in the service/schema.
- ``percentage_base`` selects whether a percentage applies to the whole total or
  only the selected components listed in ``components`` (JSONB).
- Uniqueness is a plain unique index on ``(location_id, code)`` so codes are
  unique per location regardless of active state.

Every ``downgrade()`` drops exactly what ``upgrade()`` added, in reverse order
(indexes before the table; checks/FK go with the table).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("cap_paise", sa.BigInteger(), nullable=True),
        sa.Column(
            "percentage_base",
            sa.String(),
            nullable=False,
            server_default="total",
        ),
        sa.Column("components", JSONB(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "one_time",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("total_usage_limit", sa.Integer(), nullable=True),
        sa.Column("per_customer_limit", sa.Integer(), nullable=True),
        sa.Column("min_order_paise", sa.BigInteger(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_coupons"),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_coupons_location_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "type IN ('flat','percentage')",
            name="ck_coupons_type",
        ),
        sa.CheckConstraint("value >= 0", name="ck_coupons_value_nonneg"),
        sa.CheckConstraint(
            "cap_paise IS NULL OR cap_paise >= 0",
            name="ck_coupons_cap_nonneg",
        ),
        sa.CheckConstraint(
            "percentage_base IN ('total','selected_components')",
            name="ck_coupons_percentage_base",
        ),
    )
    op.create_index(
        "uq_coupons_location_code",
        "coupons",
        ["location_id", "code"],
        unique=True,
    )
    op.create_index(
        "ix_coupons_location_id",
        "coupons",
        ["location_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_coupons_location_id", table_name="coupons")
    op.drop_index("uq_coupons_location_code", table_name="coupons")
    op.drop_table("coupons")
