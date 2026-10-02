"""Plan (decoration package = one physical room) model."""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_type: Mapped[int] = mapped_column(Integer, nullable=False)

    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    people_allowed: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    max_people_allowed: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_guest_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    give_discount: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    advance_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=text("'2099-12-31'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PlanGalleryImage(Base):
    __tablename__ = "plan_gallery_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_key: Mapped[str] = mapped_column(String, nullable=False)  # public R2 object key
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
