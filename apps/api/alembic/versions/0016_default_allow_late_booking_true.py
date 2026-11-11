"""default_allow_late_booking_true

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-11 00:30:00

Late online booking is now ALLOWED by default. Previously the column defaulted
to false (late booking off unless switched on); the product rule is the
opposite — late booking is open by default and staff disable it for the day
before signing off when there's no late-night availability.

This migration flips the column server_default to true and sets every existing
location to true so the new default applies to current branches. Staff can still
switch any branch off per day via the admin toggle.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "locations",
        "allow_late_booking",
        server_default=sa.text("true"),
    )
    # Open late booking everywhere by default for existing branches.
    op.execute("UPDATE locations SET allow_late_booking = true")


def downgrade() -> None:
    op.alter_column(
        "locations",
        "allow_late_booking",
        server_default=sa.text("false"),
    )
