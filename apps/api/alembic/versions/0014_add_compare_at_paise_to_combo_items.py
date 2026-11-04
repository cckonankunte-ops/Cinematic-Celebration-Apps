"""add_compare_at_paise_to_combo_items

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-04 00:00:00

Combo savings display (feature: combo-savings-and-addons-layout).

Additive and back-compatible: adds a nullable ``combo_items.compare_at_paise``
(the combo's "worth"/compare-at amount in paise) plus a non-negative CHECK
constraint. NULL means no worth is configured, which the API surfaces as zero
savings. This value is DISPLAY-ONLY: it never changes what a combo is charged;
it is used solely to compute the strike-through "Save ₹X" on the booking page.

No data backfill: existing combos start with NULL (zero savings) until an admin
sets a worth.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "combo_items",
        sa.Column("compare_at_paise", sa.BigInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_combo_items_compare_at_nonneg",
        "combo_items",
        "compare_at_paise IS NULL OR compare_at_paise >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_combo_items_compare_at_nonneg", "combo_items", type_="check"
    )
    op.drop_column("combo_items", "compare_at_paise")
