"""Per-duration pricing for a plan.

A plan's base price and required advance vary by slot duration (e.g. 1-hour vs
2-hour). Each row is the price for one ``(plan_id, duration_minutes)`` pair. The
people allowance and extra-guest charge do NOT vary by duration and remain on the
``plans`` row. A partial unique index enforces at most one active row per pair.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, SmallInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class PlanPricing(Base, TimestampMixin):
    __tablename__ = "plan_pricing"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    duration_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    advance_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=text("'2099-12-31'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        # At most one active price row per (plan, duration).
        Index(
            "uq_plan_pricing_active",
            "plan_id",
            "duration_minutes",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )
