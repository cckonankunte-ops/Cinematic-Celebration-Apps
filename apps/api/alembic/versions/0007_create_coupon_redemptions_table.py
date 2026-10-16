"""create_coupon_redemptions_table

Revision ID: 0007
Revises: 0006
Create Date: 2026-01-07 00:00:00

Creates the ``coupon_redemptions`` table that tracks coupon usage to enforce
``one_time``, ``total_usage_limit``, and ``per_customer_limit``.

- ``booking_id`` is unique (``uq_coupon_redemptions_booking``) so re-editing the
  same booking upserts its own row rather than double-counting.
- ``customer_key`` is the booking's Normalized_Phone; per-customer limits count
  distinct keys via the ``(coupon_id, customer_key)`` index.
- This table carries ``created_at`` only (no ``updated_at``): it is append-ish
  usage tracking.

``downgrade()`` drops exactly what ``upgrade()`` added, in reverse order
(indexes before the table; FKs/unique go with the table).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "coupon_redemptions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("coupon_id", sa.BigInteger(), nullable=False),
        sa.Column("booking_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_key", sa.String(), nullable=False),
        sa.Column("discount_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_coupon_redemptions"),
        sa.ForeignKeyConstraint(
            ["coupon_id"],
            ["coupons.id"],
            name="fk_coupon_redemptions_coupon_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name="fk_coupon_redemptions_booking_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("booking_id", name="uq_coupon_redemptions_booking"),
    )
    op.create_index(
        "ix_coupon_redemptions_coupon_id",
        "coupon_redemptions",
        ["coupon_id"],
        unique=False,
    )
    op.create_index(
        "ix_coupon_redemptions_customer",
        "coupon_redemptions",
        ["coupon_id", "customer_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_coupon_redemptions_customer", table_name="coupon_redemptions")
    op.drop_index("ix_coupon_redemptions_coupon_id", table_name="coupon_redemptions")
    op.drop_table("coupon_redemptions")
