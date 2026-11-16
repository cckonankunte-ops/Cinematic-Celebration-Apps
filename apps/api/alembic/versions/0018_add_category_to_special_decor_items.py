"""add_category_to_special_decor_items

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-16 00:00:00

Special-decor categories (feature: customer-booking-flow-v2).

Adds ``special_decor_items.category`` (TEXT, server default 'extra_decoration',
CHECK in the three allowed values) so the customer Addons step can group items
by Extra Decoration / Choose Gifts / Special Service. Stored values are
lowercase snake_case; the UI maps them to display labels.

Additive and back-compatible: existing rows backfill to 'extra_decoration' via
the server default.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "special_decor_items",
        sa.Column(
            "category",
            sa.String(),
            nullable=False,
            server_default=sa.text("'extra_decoration'"),
        ),
    )
    op.create_check_constraint(
        "ck_special_decor_items_category",
        "special_decor_items",
        "category IN ('extra_decoration', 'gifts', 'special_service')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_special_decor_items_category", "special_decor_items", type_="check"
    )
    op.drop_column("special_decor_items", "category")
