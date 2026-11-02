"""Server-authoritative pricing.

The single source of truth for all money computation. No hardcoded rupee/paise
constants — every rate comes from the plan row (the one documented exception is
``LED_UNIT_PRICE_PAISE``, the per-letter LED rate). Client-sent money is ignored.

Pricing is a pure function of already-loaded, already-validated catalog objects
(a ``ValidatedRequest``) plus an already-validated coupon value object (or
``None``). Coupon *validation* happens in the service layer first; pricing never
touches the DB or does any IO, which keeps it exhaustively property-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.cake import Cake
from app.models.combo_item import ComboItem
from app.models.plan import Plan
from app.models.special_decor_item import SpecialDecorItem

LED_UNIT_PRICE_PAISE = 4000  # single documented constant; ₹40/letter


def led_letter_count(led_name: str | None) -> int:
    """A–Z only, case-insensitive, ignoring spaces/punctuation. '' / None -> 0."""
    if not led_name:
        return 0
    return sum(1 for ch in led_name if ch.isascii() and ch.isalpha())


# COMPONENT_KEYS fixes the vocabulary for coupon 'selected_components' bases and
# for mapping each key to a concrete amount (see compute_coupon_discount).
COMPONENT_KEYS = frozenset({"plan", "extra_guest", "decor", "combos", "cake", "food"})


@dataclass(frozen=True)
class DecorSelection:
    item: SpecialDecorItem
    quantity: int  # >= 1


@dataclass(frozen=True)
class ComboSelection:
    item: ComboItem  # carries cake_baseline_paise / led_baseline_paise (nullable)
    # quantity is always 1 for combos (not stored)


@dataclass(frozen=True)
class ValidatedCoupon:
    code: str
    type: str  # 'flat' | 'percentage'
    value: int  # flat: paise; percentage: integer percent 0..100
    cap_paise: int | None
    percentage_base: str  # 'total' | 'selected_components'
    components: frozenset[str]  # subset of COMPONENT_KEYS when base == selected_components


@dataclass(frozen=True)
class ValidatedRequest:
    """Validated, de-duplicated catalog rows for a booking request."""

    plan: Plan
    people: int
    cake: Cake | None = None
    cake_weight_half_kg: int = 1  # default 1 == 0.5 kg
    special_decor: list[DecorSelection] = field(default_factory=list)
    combos: list[ComboSelection] = field(default_factory=list)
    led_name: str | None = None


@dataclass(frozen=True)
class AddonLine:
    """One add-on, captured as a name + price snapshot for booking_items."""

    kind: str  # 'cake' | 'decor' | 'combo' | 'led'
    item_id: int | None  # None for the standalone LED line
    name_snapshot: str
    unit_price_paise: int  # per-unit price snapshot
    quantity: int  # 1 for cake/combo/led; >= 1 for decor
    weight_half_kg: int | None  # set only for the cake line (half-kg units)
    # Combo transparency (set only for kind='combo'): the line's amount is the
    # combo base plus floored cake/LED upgrade deltas. Exposing the parts lets
    # the UI show the base price and each upgrade as its own sub-line instead of
    # one opaque combined figure. None for non-combo lines.
    combo_base_paise: int | None = None
    cake_upgrade_paise: int | None = None
    led_upgrade_paise: int | None = None
    # True only for a cake line whose cost is already carried by a combo's cake
    # upgrade (the cake is "absorbed" into the combo). Such a line contributes
    # ZERO to the subtotal — it exists only to persist the chosen cake id +
    # weight so an edit can reconstruct the selection. Without it, editing a
    # booking would silently drop the combo's cake upgrade.
    absorbed_by_combo: bool = False

    @property
    def amount_paise(self) -> int:
        """Line amount. Cake uses the weighted price; others use unit × qty.

        For a cake line the weight multiplier is the stored half-kg integer, so
        amount = unit_price_paise × weight_half_kg (quantity is always 1). For
        decor/combo/led, amount = unit_price_paise × quantity. An absorbed cake
        line (its cost already in a combo's upgrade) contributes 0.
        """
        if self.kind == "cake":
            if self.absorbed_by_combo:
                return 0
            return self.unit_price_paise * (self.weight_half_kg or 1)
        return self.unit_price_paise * self.quantity


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
    coupon_code: str | None
    coupon_discount_paise: int
    total_paise: int


def _extra_guest_paise(plan: Plan, people: int) -> int:
    extra_guests = max(0, people - plan.people_allowed)
    return extra_guests * plan.extra_guest_paise


def _resolve_discount(plan: Plan, requested_discount_paise: int, is_customer: bool) -> int:
    """Resolve the manual discount in paise.

    Customers never get a manual discount (always 0). The admin manual discount
    is a TRUSTED STAFF OVERRIDE: any non-negative amount is accepted, NOT gated
    by ``plan.give_discount`` and NOT capped by ``plan.max_discount_paise``. The
    total is still clamped at 0 downstream, so a discount can never make the
    booking negative.

    Note: the per-plan ``give_discount`` / ``max_discount_paise`` fields remain
    DB-driven and continue to govern the customer-facing / coupon discount path
    (see the coupon logic); they intentionally do NOT constrain this admin-only
    manual override.
    """
    if is_customer:
        return 0
    return max(0, requested_discount_paise)


def _round_half_up(numerator: int, denominator: int) -> int:
    """Integer round-half-up of numerator/denominator (both positive)."""
    return (numerator + denominator // 2) // denominator


def compute_coupon_discount(
    coupon: ValidatedCoupon,
    *,
    total_before_coupon: int,
    plan_price: int,
    extra_guest: int,
    decor_total: int,
    combo_total: int,
    cake_total: int,
    food: int,
) -> int:
    if coupon.type == "flat":
        # Flat coupons subtract a fixed paise value (never below 0; the final
        # total is clamped in compute_booking_price).
        return max(0, coupon.value)

    # percentage: value is an integer percent 0..100.
    if coupon.percentage_base == "total":
        base = max(0, total_before_coupon)
    else:  # 'selected_components' — sum ONLY the configured component amounts.
        component_amounts = {
            "plan": plan_price,
            "extra_guest": extra_guest,
            "decor": decor_total,
            "combos": combo_total,
            "cake": cake_total,
            "food": food,
        }
        base = sum(component_amounts[k] for k in coupon.components)

    raw = _round_half_up(coupon.value * base, 100)  # round(pct/100 × base) in paise
    if coupon.cap_paise is not None:
        return min(coupon.cap_paise, raw)
    return raw


def compute_booking_price(
    req: ValidatedRequest,
    *,
    discount_paise: int = 0,
    food_paise: int = 0,
    other_paise: int = 0,
    cleaning_paise: int = 0,
    is_customer: bool,
    coupon: ValidatedCoupon | None = None,
    base_price_paise: int | None = None,
) -> PriceBreakdown:
    """Compute the authoritative price breakdown.

    Steps run in order: plan + extra-guest, decor lines (unit × qty), cake
    (standalone weighted line unless a combo absorbs it), LED (standalone line
    unless a combo absorbs it), combo lines (price + floored cake/LED deltas),
    subtotal, admin discount, pre-coupon total, coupon discount, clamped total.

    ``base_price_paise`` overrides the plan's base price when the caller has
    resolved a duration-specific price (see ``services.plan_pricing``). When
    None, the plan's own ``price_paise`` is used (back-compatible default).
    People allowance and the extra-guest rate always come from the plan.
    """
    plan = req.plan
    # Duration-specific base price when provided, else the plan's price.
    plan_price = base_price_paise if base_price_paise is not None else plan.price_paise

    # 1. Plan price + extra-guest charge (extra-guest rate comes from the plan).
    extra_guest = _extra_guest_paise(plan, req.people)

    lines: list[AddonLine] = []

    # Precompute the two "variable" values combos may absorb:
    #   chosen cake weighted price, and the standalone LED charge.
    cake_weighted = req.cake.price_paise * req.cake_weight_half_kg if req.cake else 0
    led_count = led_letter_count(req.led_name)
    led_charge = led_count * LED_UNIT_PRICE_PAISE

    # Determine whether ANY selected combo absorbs cake / LED.
    combo_covers_cake = any(c.item.cake_baseline_paise is not None for c in req.combos)
    combo_covers_led = any(c.item.led_baseline_paise is not None for c in req.combos)

    # 2. Decor lines: unit_price × quantity.
    for d in req.special_decor:
        lines.append(
            AddonLine(
                kind="decor",
                item_id=d.item.id,
                name_snapshot=d.item.name,
                unit_price_paise=d.item.price_paise,
                quantity=d.quantity,
                weight_half_kg=None,
            )
        )

    # 3. Cake handling.
    #    If a selected combo has a cake baseline, the cake is priced THROUGH that
    #    combo's cake delta (step 5). We STILL emit a cake line in that case, but
    #    flagged `absorbed_by_combo` so it contributes 0 to the subtotal — it
    #    exists only to persist the chosen cake id + weight so an edit can
    #    reconstruct the selection (otherwise the combo's cake upgrade is lost on
    #    edit). Else emit a normal standalone weighted cake line.
    if req.cake is not None:
        lines.append(
            AddonLine(
                kind="cake",
                item_id=req.cake.id,
                name_snapshot=req.cake.description,
                unit_price_paise=req.cake.price_paise,
                quantity=1,
                weight_half_kg=req.cake_weight_half_kg,  # amount = base × weight_half_kg
                absorbed_by_combo=combo_covers_cake,
            )
        )

    # 4. LED handling.
    #    If a selected combo has an LED baseline, LED is priced THROUGH that
    #    combo's LED delta (step 5) — NO standalone LED line.
    #    Else, if there are letters, emit a standalone LED line.
    if led_count > 0 and not combo_covers_led:
        lines.append(
            AddonLine(
                kind="led",
                item_id=None,
                name_snapshot=req.led_name or "",
                unit_price_paise=led_charge,
                quantity=1,
                weight_half_kg=None,
            )
        )

    # 5. Combo lines: combo_price
    #       + max(0, chosen_cake_weighted − cake_baseline)  [if cake baseline]
    #       + max(0, led_charge − led_baseline)             [if led baseline]
    for c in req.combos:
        cake_upgrade = (
            max(0, cake_weighted - c.item.cake_baseline_paise)
            if c.item.cake_baseline_paise is not None
            else 0
        )
        led_upgrade = (
            max(0, led_charge - c.item.led_baseline_paise)
            if c.item.led_baseline_paise is not None
            else 0
        )
        combo_amount = c.item.price_paise + cake_upgrade + led_upgrade
        lines.append(
            AddonLine(
                kind="combo",
                item_id=c.item.id,
                name_snapshot=c.item.name,
                unit_price_paise=combo_amount,
                quantity=1,
                weight_half_kg=None,
                combo_base_paise=c.item.price_paise,
                cake_upgrade_paise=cake_upgrade,
                led_upgrade_paise=led_upgrade,
            )
        )

    # 6. Subtotal = plan + extra_guest + sum(addon amounts).
    addon_total = sum(line.amount_paise for line in lines)
    subtotal = plan_price + extra_guest + addon_total

    # 7. Admin manual discount: a trusted staff override — any non-negative
    #    amount (not gated/capped by the plan); always 0 for customers. The
    #    final total is clamped at 0 so it can't go negative.
    discount = _resolve_discount(plan, discount_paise, is_customer)
    food = max(0, food_paise)
    other = max(0, other_paise)
    cleaning = max(0, cleaning_paise)

    # 8. Pre-coupon total.
    total_before_coupon = subtotal + food + other + cleaning - discount

    # 9. Coupon discount (coupon already validated by the service layer).
    coupon_discount = 0
    coupon_code: str | None = None
    if coupon is not None:
        coupon_code = coupon.code
        coupon_discount = compute_coupon_discount(
            coupon,
            total_before_coupon=total_before_coupon,
            plan_price=plan_price,
            extra_guest=extra_guest,
            decor_total=sum(line.amount_paise for line in lines if line.kind == "decor"),
            combo_total=sum(line.amount_paise for line in lines if line.kind == "combo"),
            cake_total=sum(line.amount_paise for line in lines if line.kind == "cake"),
            food=food,
        )

    # 10. Total, clamped at 0 so a coupon can never make it negative.
    total = max(0, total_before_coupon - coupon_discount)

    return PriceBreakdown(
        plan_price_paise=plan_price,
        extra_guest_paise=extra_guest,
        addon_lines=lines,
        subtotal_paise=subtotal,
        discount_paise=discount,
        food_paise=food,
        other_paise=other,
        cleaning_paise=cleaning,
        coupon_code=coupon_code,
        coupon_discount_paise=coupon_discount,
        total_paise=total,
    )
