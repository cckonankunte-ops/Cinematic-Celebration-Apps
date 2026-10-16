"""Payment ledger (append-only). Amount due / paid are derived, never stored."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

PAYMENT_METHODS = ("cash", "upi", "card", "other")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String, nullable=False)  # cash | upi | card | other
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    recorded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str | None] = mapped_column(String, nullable=True)  # NULL in Phase 1
    provider_ref: Mapped[str | None] = mapped_column(String, nullable=True)  # NULL in Phase 1
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NULL for a normal Payment_Entry; set to the original payment's id on a
    # negative-amount Reversing_Entry. RESTRICT prevents deleting a reversed
    # original out from under its reversal. Index declared in __table_args__.
    reverses_payment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "payments.id",
            ondelete="RESTRICT",
            name="fk_payments_reverses_payment_id",
        ),
        nullable=True,
        index=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("amount_paise <> 0", name="ck_payments_amount_nonzero"),
        CheckConstraint(
            "method IN ('cash','upi','card','other')", name="ck_payments_method"
        ),
        Index("ix_payments_reverses_payment_id", "reverses_payment_id"),
    )
