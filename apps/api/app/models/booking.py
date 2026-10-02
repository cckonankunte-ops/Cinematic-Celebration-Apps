"""Booking model and the double-booking partial unique index.

One plan = one physical room, so a (location, slot, date) can be held by only one
active (pending|accepted) booking. This is enforced by the partial unique index
``uq_bookings_active_slot`` declared below.

No payment columns live here (payments are a ledger). No add-on columns live here
(add-ons are booking_items rows). No coupon_code. Amount due / paid are derived.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin

BOOKING_STATUS_VALUES = ("pending", "accepted", "rejected", "expired")

booking_status_enum = SAEnum(
    *BOOKING_STATUS_VALUES, name="booking_status", create_constraint=True
)


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_reference: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    public_token: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("slots.id", ondelete="RESTRICT"), nullable=False
    )
    booking_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # customer info
    booking_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    special_person_name: Mapped[str | None] = mapped_column(String, nullable=True)
    name_on_cake: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    people: Mapped[int] = mapped_column(Integer, nullable=False)
    occasion_id: Mapped[int | None] = mapped_column(
        ForeignKey("occasions.id", ondelete="SET NULL"), nullable=True
    )

    # money (paise, server-computed; add-on lines live in booking_items)
    plan_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    extra_guest_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    subtotal_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    food_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    other_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cleaning_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    advance_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # status + lifecycle
    status: Mapped[str] = mapped_column(
        booking_status_enum, nullable=False, default="pending", index=True
    )
    confirmation_sent_at: Mapped[date | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    crm_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        # Double-booking prevention: only one active booking per slot/date.
        Index(
            "uq_bookings_active_slot",
            "location_id",
            "slot_id",
            "booking_date",
            unique=True,
            postgresql_where=text("status IN ('pending', 'accepted')"),
        ),
        Index("ix_bookings_created_at", "created_at"),
    )
