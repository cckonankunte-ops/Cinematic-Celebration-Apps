"""Financial analytics service (admin-only surfaces).

Three reports for one location and an inclusive IST date range:

- ``slot_amounts``: bookings whose CELEBRATION date (``booking_date``) is in the
  range. Paid is the booking's whole ledger (every payment, whenever it was
  received), split by payment method. Due = total - paid.
- ``created_bookings``: bookings CREATED (``created_at``, IST) in the range,
  with plan, cake / decor / combos, total, paid and due.
- ``today_income``: payments RECEIVED (``received_at``, IST) in the range, per
  booking and per method (reversals net out). This is the cash-in-hand view.

Money stays in integer paise. Paid/due are derived from the payments ledger,
never stored. Queries are grouped (no per-booking round trips).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.core.security import CurrentUser, assert_location_access
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.payment import Payment
from app.models.plan import Plan
from app.schemas.analytics import (
    AnalyticsSummary,
    CreatedBookingRow,
    CreatedBookingsResult,
    SlotAmountRow,
    SlotAmountsResult,
    TodayIncomeResult,
    TodayIncomeRow,
    TodayIncomeSummary,
)

_IST = ZoneInfo("Asia/Kolkata")
MAX_RANGE_DAYS = 366


def validate_range(date_from: date, date_to: date) -> None:
    """Reject inverted or unreasonably wide date ranges."""
    if date_to < date_from:
        raise ValidationFailedError("'To' date cannot be before 'From' date.")
    if (date_to - date_from).days >= MAX_RANGE_DAYS:
        raise ValidationFailedError("Date range cannot exceed one year.")


def _ist_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    """Half-open ``[start, end)`` IST-aware bounds covering both whole days."""
    start = datetime.combine(date_from, time.min, tzinfo=_IST)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=_IST)
    return start, end


def _paid_by_method(
    db: Session, booking_ids: Sequence[int]
) -> dict[int, dict[str, int]]:
    """All-time ledger sums per booking per method (reversals included)."""
    out: dict[int, dict[str, int]] = defaultdict(dict)
    if not booking_ids:
        return out
    rows = db.execute(
        select(Payment.booking_id, Payment.method, func.sum(Payment.amount_paise))
        .where(Payment.booking_id.in_(booking_ids))
        .group_by(Payment.booking_id, Payment.method)
    ).all()
    for booking_id, method, amount in rows:
        out[booking_id][method] = int(amount)
    return out


def _add_methods(into: dict[str, int], methods: dict[str, int]) -> None:
    for method, amount in methods.items():
        into[method] = into.get(method, 0) + amount


def _summary(
    bookings: Sequence[Booking], paid: dict[int, dict[str, int]]
) -> AnalyticsSummary:
    by_method: dict[str, int] = {}
    total_paid = 0
    for b in bookings:
        methods = paid.get(b.id, {})
        _add_methods(by_method, methods)
        total_paid += sum(methods.values())
    total = sum(b.total_paise for b in bookings)
    return AnalyticsSummary(
        booking_count=len(bookings),
        total_paise=total,
        amount_paid_paise=total_paid,
        amount_due_paise=total - total_paid,
        discount_paise=sum(b.discount_paise for b in bookings),
        food_paise=sum(b.food_paise for b in bookings),
        cleaning_paise=sum(b.cleaning_paise for b in bookings),
        other_paise=sum(b.other_paise for b in bookings),
        paid_by_method=by_method,
    )


def slot_amounts(
    db: Session,
    actor: CurrentUser,
    *,
    location_id: int,
    date_from: date,
    date_to: date,
    statuses: Sequence[str],
) -> SlotAmountsResult:
    """Bookings celebrated in the range, with every payment they ever received."""
    assert_location_access(actor, location_id)
    validate_range(date_from, date_to)
    bookings = list(
        db.execute(
            select(Booking)
            .where(
                Booking.location_id == location_id,
                Booking.booking_date >= date_from,
                Booking.booking_date <= date_to,
                Booking.status.in_(list(statuses)),
            )
            .order_by(Booking.booking_date, Booking.id)
        ).scalars()
    )
    paid = _paid_by_method(db, [b.id for b in bookings])

    rows: list[SlotAmountRow] = []
    for b in bookings:
        methods = paid.get(b.id, {})
        paid_total = sum(methods.values())
        rows.append(
            SlotAmountRow(
                booking_name=b.booking_name,
                booking_reference=b.booking_reference,
                booking_date=b.booking_date,
                status=b.status,
                total_paise=b.total_paise,
                amount_paid_paise=paid_total,
                paid_by_method=methods,
                amount_due_paise=b.total_paise - paid_total,
                discount_paise=b.discount_paise,
                food_paise=b.food_paise,
                cleaning_paise=b.cleaning_paise,
                other_paise=b.other_paise,
            )
        )
    return SlotAmountsResult(rows=rows, summary=_summary(bookings, paid))


def _item_label(item: BookingItem) -> str:
    label = item.name_snapshot
    if item.kind == "cake" and item.weight_half_kg:
        label += f" ({item.weight_half_kg / 2:g} kg)"
    elif item.quantity > 1:
        label += f" ×{item.quantity}"
    return label


def created_bookings(
    db: Session,
    actor: CurrentUser,
    *,
    location_id: int,
    date_from: date,
    date_to: date,
    statuses: Sequence[str],
) -> CreatedBookingsResult:
    """Bookings created (IST) in the range, with what they ordered and owe."""
    assert_location_access(actor, location_id)
    validate_range(date_from, date_to)
    start, end = _ist_bounds(date_from, date_to)
    found = db.execute(
        select(Booking, Plan.title)
        .join(Plan, Plan.id == Booking.plan_id)
        .where(
            Booking.location_id == location_id,
            Booking.created_at >= start,
            Booking.created_at < end,
            Booking.status.in_(list(statuses)),
        )
        .order_by(Booking.created_at, Booking.id)
    ).all()
    bookings = [b for b, _ in found]
    ids = [b.id for b in bookings]
    paid = _paid_by_method(db, ids)

    items: dict[int, list[BookingItem]] = defaultdict(list)
    if ids:
        for item in db.execute(
            select(BookingItem)
            .where(BookingItem.booking_id.in_(ids))
            .order_by(BookingItem.id)
        ).scalars():
            items[item.booking_id].append(item)

    rows: list[CreatedBookingRow] = []
    for b, plan_title in found:
        lines = items.get(b.id, [])
        paid_total = sum(paid.get(b.id, {}).values())
        cakes = [_item_label(i) for i in lines if i.kind == "cake"]
        rows.append(
            CreatedBookingRow(
                booking_name=b.booking_name,
                booking_reference=b.booking_reference,
                created_at=b.created_at,
                booking_date=b.booking_date,
                status=b.status,
                plan_title=plan_title,
                cake=cakes[0] if cakes else None,
                special_decor=[_item_label(i) for i in lines if i.kind == "decor"],
                combos=[_item_label(i) for i in lines if i.kind == "combo"],
                total_paise=b.total_paise,
                amount_paid_paise=paid_total,
                amount_due_paise=b.total_paise - paid_total,
            )
        )
    return CreatedBookingsResult(rows=rows, summary=_summary(bookings, paid))


def today_income(
    db: Session,
    actor: CurrentUser,
    *,
    location_id: int,
    date_from: date,
    date_to: date,
    statuses: Sequence[str],
) -> TodayIncomeResult:
    """Payments received (IST) in the range, per booking and per method.

    ``statuses`` empty means every status: money physically received counts
    even if the booking was later cancelled.
    """
    assert_location_access(actor, location_id)
    validate_range(date_from, date_to)
    start, end = _ist_bounds(date_from, date_to)
    stmt = (
        select(Payment.booking_id, Payment.method, Payment.amount_paise)
        .join(Booking, Booking.id == Payment.booking_id)
        .where(
            Booking.location_id == location_id,
            Payment.received_at >= start,
            Payment.received_at < end,
        )
    )
    if statuses:
        stmt = stmt.where(Booking.status.in_(list(statuses)))
    payments = db.execute(stmt).all()

    received: dict[int, dict[str, int]] = defaultdict(dict)
    for booking_id, method, amount in payments:
        received[booking_id][method] = received[booking_id].get(method, 0) + int(amount)

    ids = list(received)
    bookings = (
        list(
            db.execute(
                select(Booking).where(Booking.id.in_(ids)).order_by(Booking.id)
            ).scalars()
        )
        if ids
        else []
    )
    paid = _paid_by_method(db, ids)

    rows: list[TodayIncomeRow] = []
    by_method: dict[str, int] = {}
    for b in bookings:
        methods = received[b.id]
        _add_methods(by_method, methods)
        paid_total = sum(paid.get(b.id, {}).values())
        rows.append(
            TodayIncomeRow(
                booking_name=b.booking_name,
                booking_reference=b.booking_reference,
                booking_date=b.booking_date,
                status=b.status,
                received_paise=sum(methods.values()),
                received_by_method=methods,
                total_paise=b.total_paise,
                amount_paid_paise=paid_total,
                amount_due_paise=b.total_paise - paid_total,
            )
        )
    summary = TodayIncomeSummary(
        booking_count=len(rows),
        payment_count=len(payments),
        received_paise=sum(r.received_paise for r in rows),
        received_by_method=by_method,
    )
    return TodayIncomeResult(rows=rows, summary=summary)
