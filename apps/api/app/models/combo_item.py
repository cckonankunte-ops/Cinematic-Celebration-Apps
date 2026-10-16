"""Combo package add-on model."""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class ComboItem(Base, TimestampMixin):
    __tablename__ = "combo_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_key: Mapped[str] = mapped_column(String, nullable=False)  # public R2 object key
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=text("'2099-12-31'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Optional baselines: NULL means the combo does not include that component.
    cake_baseline_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    led_baseline_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "cake_baseline_paise IS NULL OR cake_baseline_paise >= 0",
            name="ck_combo_items_cake_baseline_nonneg",
        ),
        CheckConstraint(
            "led_baseline_paise IS NULL OR led_baseline_paise >= 0",
            name="ck_combo_items_led_baseline_nonneg",
        ),
    )
