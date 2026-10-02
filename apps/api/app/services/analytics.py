"""Daily financial analytics service (admin-only surfaces).

Two reports per location + date:

- ``slot_amounts``: every non-rejected booking on a ``booking_date`` with its
  total, paid (from the ledger), today's income, derived amount due, and the
  per-category charge columns, plus a day summary (column sums).
- ``advance_amounts``: bookings whose ``created_at`` falls on the given date
  (advances taken that day) with total and paid, plus a day summary.

Money stays in integer paise. Due/paid are derived from the payments ledger,
never stored (see ``services.payments``).
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, assert_location_access
from app.models.booking import Booking
from app.schemas.analytics import (
    AdvanceAmountRow,
    AdvanceAmountsResult,
    AnalyticsDaySummary,
    SlotAmountRow,
    SlotAmountsResult,
)
from app.services import payments as payments_service

_IST = ZoneInfo("Asia/Kolkata")


def _day_bounds_utc(on_date: date) -> tuple[datetime, datetime]:
    """Return [start, end) UTC datetimes spanning an Asia/Kolkata calendar day.

    ``created_at`` is stored in UTC; an IST day maps to a UTC half-open window.
    """
    start_ist = datetime.combine(on_date, time.min, tzinfo=_IST)
    end_ist = datetime.combine(on_date, time.max, tzinfo=_IST)
    return start_ist, end_ist


def slot_amounts(
    db: Session, actor: CurrentUser, *, location_id: int, on_date: date
) -> SlotAmountsResult:
    """Non-rejected bookings on ``on_date`` with money columns + a day summary."""
    assert_location_access(actor, location_id)
    bookings = list(
        db.execute(
            select(Booking)
            .where(
                Booking.location_id == location_id,
                Booking.booking_date == on_date,
                Booking.status != "rejected",
            )
            .order_by(Booking.id)
        ).scalars()
    )

    rows: list[SlotAmountRow] = []
    for booking in bookings:
        amounts = payments_service.derive_amounts_for_booking(db, booking)
        rows.append(
            SlotAmountRow(
                booking_name=booking.booking_name,
                booking_reference=booking.booking_reference,
                total_paise=booking.total_paise,
                amount_paid_paise=amounts.amount_paid_paise,
                today_income_paise=amounts.amount_paid_paise,
                amount_due_paise=amounts.amount_due_paise,
                discount_paise=booking.discount_paise,
                food_paise=booking.food_paise,
                cleaning_paise=booking.cleaning_paise,
                other_paise=booking.other_paise,
                created_at=booking.created_at,
            )
        )

    summary = AnalyticsDaySummary(
        total_paise=sum(r.total_paise for r in rows),
        amount_paid_paise=sum(r.amount_paid_paise for r in rows),
        amount_due_paise=sum(r.amount_due_paise for r in rows),
        discount_paise=sum(r.discount_paise for r in rows),
        food_paise=sum(r.food_paise for r in rows),
        cleaning_paise=sum(r.cleaning_paise for r in rows),
        other_paise=sum(r.other_paise for r in rows),
    )
    return SlotAmountsResult(rows=rows, summary=summary)


def advance_amounts(
    db: Session, actor: CurrentUser, *, location_id: int, on_date: date
) -> AdvanceAmountsResult:
    """Bookings created on ``on_date`` (advances taken that day) + a day summary."""
    assert_location_access(actor, location_id)
    start, end = _day_bounds_utc(on_date)
    bookings = list(
        db.execute(
            select(Booking)
            .where(
                Booking.location_id == location_id,
                Booking.created_at >= start,
                Booking.created_at <= end,
                Booking.status != "rejected",
            )
            .order_by(Booking.created_at, Booking.id)
        ).scalars()
    )

    rows: list[AdvanceAmountRow] = []
    for booking in bookings:
        amounts = payments_service.derive_amounts_for_booking(db, booking)
        rows.append(
            AdvanceAmountRow(
                booking_name=booking.booking_name,
                booking_reference=booking.booking_reference,
                total_paise=booking.total_paise,
                amount_paid_paise=amounts.amount_paid_paise,
                created_at=booking.created_at,
            )
        )

    summary = AnalyticsDaySummary(
        total_paise=sum(r.total_paise for r in rows),
        amount_paid_paise=sum(r.amount_paid_paise for r in rows),
        amount_due_paise=sum(r.total_paise - r.amount_paid_paise for r in rows),
        discount_paise=0,
        food_paise=0,
        cleaning_paise=0,
        other_paise=0,
    )
    return AdvanceAmountsResult(rows=rows, summary=summary)
