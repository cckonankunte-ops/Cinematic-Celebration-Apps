"""Booking add-on line items (name + price snapshots captured at booking time)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

BOOKING_ITEM_KINDS = ("cake", "decor", "combo")


class BookingItem(Base):
    __tablename__ = "booking_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)  # cake | decor | combo
    # Nullable: source catalog item may later be deactivated/removed; snapshot survives.
    item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("kind IN ('cake','decor','combo')", name="ck_booking_items_kind"),
    )
