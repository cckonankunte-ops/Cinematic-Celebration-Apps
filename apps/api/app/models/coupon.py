"""Coupon model: location-scoped, admin-managed flat/percentage discounts.

``value`` holds paise for ``flat`` coupons and an integer percent (0-100) for
``percentage`` coupons; the DB enforces only ``value >= 0`` while the
percentage upper bound (``<= 100``) is type-dependent and enforced in the
service/schema layer. ``components`` (JSONB) lists which components a percentage
applies to when ``percentage_base='selected_components'`` and is ignored/NULL
when ``percentage_base='total'``. Codes are unique per location regardless of
active state (``uq_coupons_location_code``).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    location_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("locations.id", ondelete="RESTRICT", name="fk_coupons_location_id"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # flat | percentage
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cap_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    percentage_base: Mapped[str] = mapped_column(
        String, nullable=False, server_default="total"
    )  # total | selected_components
    components: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    one_time: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    total_usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_customer_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_order_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ('flat','percentage')",
            name="ck_coupons_type",
        ),
        CheckConstraint("value >= 0", name="ck_coupons_value_nonneg"),
        CheckConstraint(
            "cap_paise IS NULL OR cap_paise >= 0",
            name="ck_coupons_cap_nonneg",
        ),
        CheckConstraint(
            "percentage_base IN ('total','selected_components')",
            name="ck_coupons_percentage_base",
        ),
        UniqueConstraint("location_id", "code", name="uq_coupons_location_code"),
        Index("ix_coupons_location_id", "location_id"),
    )
