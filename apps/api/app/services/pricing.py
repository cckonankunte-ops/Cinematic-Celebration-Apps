"""Server-authoritative pricing.

The single source of truth for all money computation. No hardcoded rupee/paise
constants — every rate comes from the plan row. Client-sent money is ignored.

Pricing is a pure function of already-loaded, already-validated catalog objects
(a ``ValidatedRequest``). Task 10's ``validate_booking_request`` builds that
object; keeping pricing pure makes it exhaustively property-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.cake import Cake
from app.models.combo_item import ComboItem
from app.models.plan import Plan
from app.models.special_decor_item import SpecialDecorItem


@dataclass(frozen=True)
class ValidatedRequest:
    """Validated, de-duplicated catalog rows for a booking request."""

    plan: Plan
    people: int
    cake: Cake | None = None
    special_decor: list[SpecialDecorItem] = field(default_factory=list)
    combos: list[ComboItem] = field(default_factory=list)


@dataclass(frozen=True)
class AddonLine:
    """One add-on, captured as a name + price snapshot for booking_items."""

    kind: str  # 'cake' | 'decor' | 'combo'
    item_id: int
    name_snapshot: str
    price_paise: int


@dataclass(frozen=True)
class PriceBreakdown:
    plan_price_paise: int
    extra_guest_paise: int
    addon_lines: list[AddonLine]
    subtotal_paise: int
    discount_paise: int
    food_paise: int
    other_paise: int
    cleaning_paise: int
    total_paise: int


def _extra_guest_paise(plan: Plan, people: int) -> int:
    extra_guests = max(0, people - plan.people_allowed)
    return extra_guests * plan.extra_guest_paise


def _addon_lines(req: ValidatedRequest) -> list[AddonLine]:
    lines: list[AddonLine] = []
    if req.cake is not None:
        lines.append(
            AddonLine("cake", req.cake.id, req.cake.description, req.cake.price_paise)
        )
    for d in req.special_decor:
        lines.append(AddonLine("decor", d.id, d.name, d.price_paise))
    for c in req.combos:
        lines.append(AddonLine("combo", c.id, c.name, c.price_paise))
    return lines


def _resolve_discount(plan: Plan, requested_discount_paise: int, is_customer: bool) -> int:
    """Customer discount is always 0; admin discount is clamped and gated."""
    if is_customer:
        return 0
    if not plan.give_discount:
        return 0
    return min(max(0, requested_discount_paise), plan.max_discount_paise)


def compute_booking_price(
    req: ValidatedRequest,
    *,
    discount_paise: int = 0,
    food_paise: int = 0,
    other_paise: int = 0,
    cleaning_paise: int = 0,
    is_customer: bool,
) -> PriceBreakdown:
    """Compute the authoritative price breakdown.

    total = plan_price
          + max(0, people - people_allowed) * extra_guest_rate
          + sum(addon prices)
          + food + other + cleaning
          - discount
    where discount is 0 for customers, and for admins is
    min(requested, plan.max_discount_paise) only if plan.give_discount else 0.
    """
    plan = req.plan
    extra_guest = _extra_guest_paise(plan, req.people)
    lines = _addon_lines(req)
    addon_total = sum(line.price_paise for line in lines)
    subtotal = plan.price_paise + extra_guest + addon_total

    discount = _resolve_discount(plan, discount_paise, is_customer)
    food = max(0, food_paise)
    other = max(0, other_paise)
    cleaning = max(0, cleaning_paise)
    total = subtotal + food + other + cleaning - discount

    return PriceBreakdown(
        plan_price_paise=plan.price_paise,
        extra_guest_paise=extra_guest,
        addon_lines=lines,
        subtotal_paise=subtotal,
        discount_paise=discount,
        food_paise=food,
        other_paise=other,
        cleaning_paise=cleaning,
        total_paise=total,
    )
