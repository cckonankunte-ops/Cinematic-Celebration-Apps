"""add_kid_price_pct_to_plans

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-16 00:00:00

Kids pricing (feature: customer-booking-flow-v2).

Adds ``plans.kid_price_pct`` (SMALLINT, server default 50, CHECK 0..100): the
percentage of the plan's CURRENT extra-guest rate charged per kid (3-10 yrs).
Because the kid charge is derived from ``extra_guest_paise`` at pricing time,
raising the adult rate later automatically raises the kid charge.

Additive and back-compatible: the server default of 50 backfills existing rows
(kids = half the adult extra-guest rate), matching the owner's reference
example (adult Rs.150 -> kid Rs.75).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column(
            "kid_price_pct",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("50"),
        ),
    )
    op.create_check_constraint(
        "ck_plans_kid_price_pct_range",
        "plans",
        "kid_price_pct BETWEEN 0 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint("ck_plans_kid_price_pct_range", "plans", type_="check")
    op.drop_column("plans", "kid_price_pct")
