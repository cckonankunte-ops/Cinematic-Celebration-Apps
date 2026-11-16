"""add_name_description_public_to_coupons

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-16 00:00:00

Home-page coupon offers (feature: customer-booking-flow-v2).

Adds three columns to ``coupons``:
- ``name`` (TEXT NULL): admin-written short offer label.
- ``description`` (TEXT NULL): admin-written plain-text blurb shown to customers.
- ``is_public`` (BOOLEAN NOT NULL default false): only public coupons appear in
  the home-page offers showcase.

Additive and back-compatible: existing coupons default to private
(is_public = false) so nothing is exposed until an admin opts a coupon in.
``name``/``description`` are display-only and never affect discount math.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("coupons", sa.Column("name", sa.String(), nullable=True))
    op.add_column("coupons", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "coupons",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("coupons", "is_public")
    op.drop_column("coupons", "description")
    op.drop_column("coupons", "name")
