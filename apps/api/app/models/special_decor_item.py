"""Special decor add-on model."""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin

# Allowed special-decor categories (stored lowercase snake_case; the UI maps to
# display labels: extra_decoration -> "Extra Decoration", gifts -> "Choose
# Gifts", special_service -> "Special Service").
SPECIAL_DECOR_CATEGORIES = (
    "extra_decoration",
    "gifts",
    "special_service",
    "admin_only",  # staff-only; hidden from and rejected for customers
)


class SpecialDecorItem(Base, TimestampMixin):
    __tablename__ = "special_decor_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Grouping category shown on the customer Addons step. Defaults to
    # extra_decoration for existing/migrated rows.
    category: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'extra_decoration'")
    )
    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_key: Mapped[str] = mapped_column(String, nullable=False)  # public R2 object key
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=text("'2099-12-31'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "category IN ('extra_decoration', 'gifts', 'special_service', 'admin_only')",
            name="ck_special_decor_items_category",
        ),
    )
