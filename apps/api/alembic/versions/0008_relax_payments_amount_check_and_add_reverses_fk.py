"""relax_payments_amount_check_and_add_reverses_fk

Revision ID: 0008
Revises: 0007
Create Date: 2026-01-08 00:00:00

Extends the append-only ``payments`` ledger so a payment can be voided by
inserting a negative-amount Reversing_Entry that references the original row:

- The amount CHECK is **relaxed** from ``amount_paise > 0`` to
  ``amount_paise <> 0`` so a Reversing_Entry may be negative while a zero amount
  stays rejected. The check is renamed ``ck_payments_amount_positive`` ->
  ``ck_payments_amount_nonzero`` for accuracy.
- ``reverses_payment_id`` (self-FK -> ``payments.id``, ``ON DELETE RESTRICT``)
  is NULL for a normal Payment_Entry and set to the original payment's id on a
  Reversing_Entry; ``RESTRICT`` prevents deleting a reversed original.

Downgrade note (tightening-on-downgrade, documented precedent like 0002/0005).
The upgrade is a pure widening (``<> 0`` admits every row ``> 0`` already
satisfies), so it never fails. The downgrade drops the index, the self-FK, and
the ``reverses_payment_id`` column, then drops ``ck_payments_amount_nonzero``
and re-adds ``ck_payments_amount_positive`` (``amount_paise > 0``). Re-adding
the stricter ``> 0`` check **can only succeed if no negative (reversing) rows
exist**; dropping ``reverses_payment_id`` first removes the only way a negative
row could have been created, but any negative rows already persisted must be
removed before the downgrade can re-add ``> 0``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_payments_amount_positive", "payments", type_="check")
    op.create_check_constraint(
        "ck_payments_amount_nonzero", "payments", "amount_paise <> 0"
    )
    op.add_column(
        "payments",
        sa.Column("reverses_payment_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_payments_reverses_payment_id",
        "payments",
        "payments",
        ["reverses_payment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_payments_reverses_payment_id",
        "payments",
        ["reverses_payment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_payments_reverses_payment_id", table_name="payments")
    op.drop_constraint(
        "fk_payments_reverses_payment_id", "payments", type_="foreignkey"
    )
    op.drop_column("payments", "reverses_payment_id")
    op.drop_constraint("ck_payments_amount_nonzero", "payments", type_="check")
    # Re-adding the stricter `> 0` check only succeeds if no non-positive
    # (reversing) rows exist (see module docstring for the rationale).
    op.create_check_constraint(
        "ck_payments_amount_positive", "payments", "amount_paise > 0"
    )
