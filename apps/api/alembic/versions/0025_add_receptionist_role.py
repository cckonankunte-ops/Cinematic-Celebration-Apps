"""add_receptionist_role

Revision ID: 0025
Revises: 0024

Adds the 'receptionist' user role: everything staff can do, plus the lead CRM
(staff no longer see leads). Data-only; the insert is skipped if the role
already exists, so it is safe on any database.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO user_roles (name) "
        "SELECT 'receptionist' "
        "WHERE NOT EXISTS (SELECT 1 FROM user_roles WHERE name = 'receptionist')"
    )


def downgrade() -> None:
    # users.role_id is ON DELETE RESTRICT: if anyone still has the role this
    # fails loudly instead of leaving users without a role. Move them first.
    op.execute("DELETE FROM user_roles WHERE name = 'receptionist'")
