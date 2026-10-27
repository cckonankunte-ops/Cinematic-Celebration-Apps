"""add_led_name_coupon_snapshot_and_nullable_email_to_bookings

Revision ID: 0005
Revises: 0004
Create Date: 2026-01-05 00:00:00

Adds LED text and an applied-coupon snapshot to ``bookings`` and flips the
contact-field rule so email becomes optional:

- ``led_name`` (``Text NULL``) — the LED text (e.g. "ARUNA"); may be absent.
- ``coupon_code`` (``String NULL``) — snapshot of the applied coupon code,
  ``NULL`` when none applied.
- ``coupon_discount_paise`` (``BigInteger NOT NULL DEFAULT 0``) — the
  server-computed coupon discount, independent of ``discount_paise`` (the admin
  manual discount).
- ``email`` is **altered from NOT NULL to NULL**. Making a NOT NULL column
  nullable is a safe widening that never fails on existing rows, so no forward
  backfill is required (new ``coupon_discount_paise`` relies on its default 0).

Downgrade note (tightening-on-downgrade, documented like 0002/0008/0009):
restoring ``email NOT NULL`` can only succeed if no row has a null email. Any
booking persisted with a null email after this upgrade is therefore backfilled
to ``''`` inside ``downgrade()`` *before* re-adding the NOT NULL constraint, so
the reversal cannot fail. ``phone`` is intentionally left nullable at the DB
level (phone-required is enforced at the schema/service layer).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("led_name", sa.Text(), nullable=True))
    op.add_column("bookings", sa.Column("coupon_code", sa.String(), nullable=True))
    op.add_column(
        "bookings",
        sa.Column(
            "coupon_discount_paise",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    # Safe widening: NOT NULL -> NULL never fails on existing rows.
    op.alter_column("bookings", "email", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Backfill null emails before restoring NOT NULL so the reversal cannot
    # fail. Any booking persisted with a null email after the upgrade is set to
    # '' here (see module docstring for the tightening-on-downgrade rationale).
    op.execute("UPDATE bookings SET email = '' WHERE email IS NULL")
    op.alter_column("bookings", "email", existing_type=sa.String(), nullable=False)
    op.drop_column("bookings", "coupon_discount_paise")
    op.drop_column("bookings", "coupon_code")
    op.drop_column("bookings", "led_name")
