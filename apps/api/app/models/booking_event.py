"""Append-only booking audit trail.

Exactly one row is written in the same transaction as every booking state change
(created, accepted, rejected, edited, payment_recorded, expired).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

BOOKING_EVENT_TYPES = (
    "created",
    "accepted",
    "rejected",
    "edited",
    "payment_recorded",
    "expired",
)


class BookingEvent(Base):
    __tablename__ = "booking_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )  # NULL = system/customer
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created','accepted','rejected','edited',"
            "'payment_recorded','expired')",
            name="ck_booking_events_type",
        ),
    )
