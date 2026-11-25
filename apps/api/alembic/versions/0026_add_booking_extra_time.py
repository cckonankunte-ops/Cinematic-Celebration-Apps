"""add_booking_extra_time

Revision ID: 0026
Revises: 0025

Admin-only "extra time" on open-mode bookings: ``extra_minutes`` lengthens the
booking window past its priced duration, and ``extra_time_price_paise`` is the
flat charge for it.

``occupied_range`` is a GENERATED column, so it cannot be altered in place. The
overlap exclusion constraint depends on it, so this migration drops the
constraint and the column, adds the new columns, then recreates both with the
range now covering ``duration_minutes + extra_minutes``. Existing rows get 0
extra minutes, so their ranges are unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_range_and_constraint(include_extra: bool) -> None:
    minutes = "duration_minutes + extra_minutes" if include_extra else "duration_minutes"
    op.execute(
        f"""
        ALTER TABLE bookings
        ADD COLUMN occupied_range tsrange
        GENERATED ALWAYS AS (
            tsrange(
                (booking_date + start_time),
                (booking_date + start_time) + make_interval(mins => {minutes}),
                '[)'
            )
        ) STORED
        """
    )
    op.execute(
        """
        ALTER TABLE bookings
        ADD CONSTRAINT excl_bookings_active_overlap
        EXCLUDE USING gist (
            location_id WITH =,
            plan_id WITH =,
            occupied_range WITH &&
        ) WHERE (status IN ('pending','accepted'))
        """
    )


def upgrade() -> None:
    op.execute("ALTER TABLE bookings DROP CONSTRAINT excl_bookings_active_overlap")
    op.execute("ALTER TABLE bookings DROP COLUMN occupied_range")

    op.add_column(
        "bookings",
        sa.Column(
            "extra_minutes", sa.SmallInteger(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.add_column(
        "bookings",
        sa.Column(
            "extra_time_price_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "ck_bookings_extra_minutes_nonneg", "bookings", "extra_minutes >= 0"
    )
    op.create_check_constraint(
        "ck_bookings_extra_time_price_nonneg", "bookings", "extra_time_price_paise >= 0"
    )

    _add_range_and_constraint(include_extra=True)


def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP CONSTRAINT excl_bookings_active_overlap")
    op.execute("ALTER TABLE bookings DROP COLUMN occupied_range")

    op.drop_constraint("ck_bookings_extra_time_price_nonneg", "bookings", type_="check")
    op.drop_constraint("ck_bookings_extra_minutes_nonneg", "bookings", type_="check")
    op.drop_column("bookings", "extra_time_price_paise")
    op.drop_column("bookings", "extra_minutes")

    _add_range_and_constraint(include_extra=False)
