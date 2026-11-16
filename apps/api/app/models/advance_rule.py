"""Per-branch, threshold-based advance rules.

Each row says: when a booking's FINAL total (after all discounts and coupon)
is at least ``min_total_paise``, the advance payable is ``advance_paise``. The
pricing layer picks exactly one rule — the highest ``min_total_paise`` the final
total meets — and falls back to the plan's ``advance_paise`` when no rule
matches. Thresholds are unique per location so the "one rule wins" selection is
deterministic. Rules are forward-looking: applied at preview/creation time only.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class AdvanceRule(Base, TimestampMixin):
    __tablename__ = "advance_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The rule matches when the booking's final total >= min_total_paise.
    min_total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # The advance to charge when this rule wins.
    advance_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    __table_args__ = (
        CheckConstraint(
            "min_total_paise >= 0", name="ck_advance_rules_min_total_nonneg"
        ),
        CheckConstraint(
            "advance_paise >= 0", name="ck_advance_rules_advance_nonneg"
        ),
        # One rule per threshold per branch -> deterministic "highest match wins".
        UniqueConstraint(
            "location_id",
            "min_total_paise",
            name="uq_advance_rules_location_threshold",
        ),
        Index("ix_advance_rules_location_id", "location_id"),
    )
