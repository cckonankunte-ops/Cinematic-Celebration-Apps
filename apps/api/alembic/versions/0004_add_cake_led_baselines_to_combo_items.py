"""add_cake_led_baselines_to_combo_items

Revision ID: 0004
Revises: 0003
Create Date: 2026-01-04 00:00:00

Adds two optional baseline columns to ``combo_items`` so an admin-managed combo
can absorb a cake and/or an LED component with floored "upgrade delta" pricing:

- ``cake_baseline_paise`` (``BigInteger NULL``) — ``NULL`` means the combo does
  not include a cake. Guarded by ``cake_baseline_paise IS NULL OR
  cake_baseline_paise >= 0`` named ``ck_combo_items_cake_baseline_nonneg``.
- ``led_baseline_paise`` (``BigInteger NULL``) — ``NULL`` means the combo does
  not include LED. Guarded by ``led_baseline_paise IS NULL OR
  led_baseline_paise >= 0`` named ``ck_combo_items_led_baseline_nonneg``.

No backfill is needed: existing combos get ``NULL`` on both columns, matching
the prior behaviour where a combo was a flat priced line with no cake/LED
component. Downgrade drops both checks then both columns.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "combo_items",
        sa.Column("cake_baseline_paise", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "combo_items",
        sa.Column("led_baseline_paise", sa.BigInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_combo_items_cake_baseline_nonneg",
        "combo_items",
        "cake_baseline_paise IS NULL OR cake_baseline_paise >= 0",
    )
    op.create_check_constraint(
        "ck_combo_items_led_baseline_nonneg",
        "combo_items",
        "led_baseline_paise IS NULL OR led_baseline_paise >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_combo_items_led_baseline_nonneg", "combo_items", type_="check"
    )
    op.drop_constraint(
        "ck_combo_items_cake_baseline_nonneg", "combo_items", type_="check"
    )
    op.drop_column("combo_items", "led_baseline_paise")
    op.drop_column("combo_items", "cake_baseline_paise")
