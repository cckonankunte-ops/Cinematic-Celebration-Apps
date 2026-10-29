"""add_map_url_to_locations

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-29 00:00:00

Adds ``map_url`` (``Text NULL``) to ``locations`` — the Google Maps share link
shown to customers (e.g. in the WhatsApp booking-confirmation message). Nullable
additive column; no backfill required.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("locations", sa.Column("map_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("locations", "map_url")
