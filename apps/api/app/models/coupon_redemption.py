"""Coupon redemption model: usage tracking for coupon limit enforcement.

Tracks usage to enforce ``one_time``, ``total_usage_limit``, and
``per_customer_limit``. ``booking_id`` is unique so re-editing a booking that
already redeemed a coupon upserts its own row rather than consuming a second
use. ``customer_key`` is the booking's Normalized_Phone; per-customer limits
count distinct keys via the ``(coupon_id, customer_key)`` index. This table
carries ``created_at`` only (no ``updated_at`` / ``TimestampMixin``) because it
is append-ish usage tracking.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    coupon_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "coupons.id",
            ondelete="CASCADE",
            name="fk_coupon_redemptions_coupon_id",
        ),
        nullable=False,
    )
    booking_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "bookings.id",
            ondelete="CASCADE",
            name="fk_coupon_redemptions_booking_id",
        ),
        nullable=False,
    )
    customer_key: Mapped[str] = mapped_column(String, nullable=False)
    discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_coupon_redemptions_booking"),
        Index("ix_coupon_redemptions_coupon_id", "coupon_id"),
        Index("ix_coupon_redemptions_customer", "coupon_id", "customer_key"),
    )
