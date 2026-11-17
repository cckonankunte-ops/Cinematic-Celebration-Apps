"""add_admin_only_decor_category

Revision ID: 0023
Revises: 0022

Adds 'admin_only' to the special_decor_items.category CHECK. Items in this
category are only selectable by staff in the admin booking form and are hidden
from (and rejected for) customers.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAME = "ck_special_decor_items_category"
_TABLE = "special_decor_items"


def upgrade() -> None:
    op.drop_constraint(_NAME, _TABLE, type_="check")
    op.create_check_constraint(
        _NAME,
        _TABLE,
        "category IN ('extra_decoration', 'gifts', 'special_service', 'admin_only')",
    )


def downgrade() -> None:
    # Fold any admin-only rows back into a valid legacy category first.
    op.execute(
        "UPDATE special_decor_items SET category = 'extra_decoration' "
        "WHERE category = 'admin_only'"
    )
    op.drop_constraint(_NAME, _TABLE, type_="check")
    op.create_check_constraint(
        _NAME,
        _TABLE,
        "category IN ('extra_decoration', 'gifts', 'special_service')",
    )
