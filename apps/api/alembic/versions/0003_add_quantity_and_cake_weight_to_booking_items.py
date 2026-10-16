"""add_quantity_and_cake_weight_to_booking_items

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-03 00:00:00

Adds add-on quantity and cake-weight pricing support to ``booking_items``:

- ``quantity`` (``Integer NOT NULL DEFAULT 1``) with a ``quantity >= 1`` check
  named ``ck_booking_items_quantity_positive``. Cake lines always carry ``1``;
  decor/combo lines may carry more.
- ``weight_half_kg`` (``SmallInteger NULL``) storing cake weight in half-kg
  units (``1 = 0.5 kg``), non-null only for ``kind='cake'`` rows, guarded by
  ``weight_half_kg IS NULL OR weight_half_kg >= 1`` named
  ``ck_booking_items_weight_positive``.

Backfill is forward-only: every existing row gets ``quantity = 1`` and cake
rows get ``weight_half_kg = 1`` (non-cake rows stay NULL). The existing
``ck_booking_items_kind`` check is left unchanged. Downgrade simply drops the
two new checks and the two new columns, so there is no tightening-on-downgrade
hazard.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "booking_items",
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "booking_items",
        sa.Column("weight_half_kg", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_booking_items_quantity_positive", "booking_items", "quantity >= 1"
    )
    op.create_check_constraint(
        "ck_booking_items_weight_positive",
        "booking_items",
        "weight_half_kg IS NULL OR weight_half_kg >= 1",
    )

    # Forward-only backfill. The server_default already fills quantity on new
    # rows; this is explicit for existing rows. Cake rows get a 0.5 kg default
    # weight; non-cake rows remain NULL (no weight component).
    op.execute("UPDATE booking_items SET quantity = 1")
    op.execute("UPDATE booking_items SET weight_half_kg = 1 WHERE kind = 'cake'")


def downgrade() -> None:
    op.drop_constraint(
        "ck_booking_items_weight_positive", "booking_items", type_="check"
    )
    op.drop_constraint(
        "ck_booking_items_quantity_positive", "booking_items", type_="check"
    )
    op.drop_column("booking_items", "weight_half_kg")
    op.drop_column("booking_items", "quantity")
