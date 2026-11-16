"""add_kids_to_bookings

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-16 00:00:00

Kids / adults guest split (feature: customer-booking-flow-v2).

Adds ``bookings.kids`` (SMALLINT, server default 0, CHECK ``kids >= 0``).
``bookings.people`` remains the ADULT count; total guests = people + kids. This
preserves every existing reader of ``people`` and the extra-guest snapshot;
kids pricing is a separate charge computed server-side in pricing.py.

Additive and back-compatible: existing/migrated rows backfill to kids = 0 via
the server default.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column(
            "kids",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "ck_bookings_kids_nonneg",
        "bookings",
        "kids >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_bookings_kids_nonneg", "bookings", type_="check")
    op.drop_column("bookings", "kids")
