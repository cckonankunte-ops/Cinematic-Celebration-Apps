"""Resolve the base price + advance for a (plan, duration) on a date.

Price and advance vary by slot duration (R11). This resolver looks up the active
``plan_pricing`` row for ``(plan_id, duration_minutes)`` valid on the booking
date; when none exists it falls back to the plan's own ``price_paise`` /
``advance_paise`` so plans without per-duration rows still price correctly.

People allowance and the extra-guest charge are NOT resolved here — they remain
plan-level and are read directly from the plan by ``services.pricing``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.plan_pricing import PlanPricing


@dataclass(frozen=True)
class DurationPricing:
    """Base price + advance for a specific plan+duration (integer paise)."""

    price_paise: int
    advance_paise: int


def resolve_duration_pricing(
    db: Session, plan: Plan, duration_minutes: int | None, on: date
) -> DurationPricing:
    """Return the price+advance for the plan at the given duration on a date.

    Falls back to the plan's own price/advance when ``duration_minutes`` is None
    or no active ``plan_pricing`` row matches.
    """
    if duration_minutes is not None:
        row = db.execute(
            select(PlanPricing).where(
                PlanPricing.plan_id == plan.id,
                PlanPricing.duration_minutes == duration_minutes,
                PlanPricing.is_active.is_(True),
                PlanPricing.effective_from <= on,
                PlanPricing.effective_to >= on,
            )
        ).scalar_one_or_none()
        if row is not None:
            return DurationPricing(
                price_paise=row.price_paise, advance_paise=row.advance_paise
            )
    return DurationPricing(
        price_paise=plan.price_paise, advance_paise=plan.advance_paise
    )
