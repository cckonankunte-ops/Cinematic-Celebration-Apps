"""Slot (time window within a plan) model."""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import Boolean, Date, ForeignKey, Integer, SmallInteger, String, Time, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class Slot(Base, TimestampMixin):
    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String, nullable=False)  # "9 AM - 12 PM"
    # Machine-readable slot time (IST wall-clock). Nullable during the retrofit;
    # becomes NOT NULL after backfill (see time-range-slots spec, migration B).
    # start_time minute must be 00 or 30 (enforced by a later CHECK + validation).
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    show_combos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=text("'2099-12-31'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
