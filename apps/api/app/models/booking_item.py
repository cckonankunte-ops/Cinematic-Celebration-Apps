"""Booking add-on line items (name + price snapshots captured at booking time)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
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
    # Add-on quantity: cake lines always 1; decor/combo lines may be >= 1.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    # Cake weight in half-kg units (1 = 0.5 kg); non-null only for kind='cake'.
    weight_half_kg: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("kind IN ('cake','decor','combo')", name="ck_booking_items_kind"),
        CheckConstraint("quantity >= 1", name="ck_booking_items_quantity_positive"),
        CheckConstraint(
            "weight_half_kg IS NULL OR weight_half_kg >= 1",
            name="ck_booking_items_weight_positive",
        ),
    )
