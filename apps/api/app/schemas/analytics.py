"""Analytics schemas (admin-only).

All money stays in integer paise. ``amount_due_paise`` may be negative to
represent overpayment (mirrors ``DerivedAmounts`` in the payments schema).

``*_by_method`` maps are keyed by payment method (cash, upi, card, other, and
any method added later) so new methods flow through without schema changes.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

BookingStatusName = Literal["pending", "accepted", "rejected", "expired", "cancelled"]


class AnalyticsSummary(BaseModel):
    """Column sums for the bookings in a report."""

    booking_count: int
    total_paise: int
    amount_paid_paise: int
    amount_due_paise: int
    discount_paise: int
    food_paise: int
    cleaning_paise: int
    other_paise: int
    paid_by_method: dict[str, int]


# --- Slot amount: bookings whose celebration date is in the range -----------
class SlotAmountRow(BaseModel):
    booking_name: str
    booking_reference: str
    booking_date: date
    status: str
    total_paise: int
    amount_paid_paise: int  # ALL payments for the booking, regardless of received date
    paid_by_method: dict[str, int]
    amount_due_paise: int  # may be negative = overpaid
    discount_paise: int
    food_paise: int
    cleaning_paise: int
    other_paise: int


class SlotAmountsResult(BaseModel):
    rows: list[SlotAmountRow]
    summary: AnalyticsSummary


# --- Bookings created: bookings whose created_at (IST) is in the range ------
class CreatedBookingRow(BaseModel):
    booking_name: str
    booking_reference: str
    created_at: datetime
    booking_date: date
    status: str
    plan_title: str
    cake: str | None
    special_decor: list[str]
    combos: list[str]
    total_paise: int
    amount_paid_paise: int
    amount_due_paise: int  # may be negative = overpaid


class CreatedBookingsResult(BaseModel):
    rows: list[CreatedBookingRow]
    summary: AnalyticsSummary


# --- Today income: payments received in the range ---------------------------
class TodayIncomeRow(BaseModel):
    booking_name: str
    booking_reference: str
    booking_date: date
    status: str
    received_paise: int  # net of reversals, received in the range
    received_by_method: dict[str, int]
    total_paise: int
    amount_paid_paise: int  # all-time paid for the booking
    amount_due_paise: int


class TodayIncomeSummary(BaseModel):
    booking_count: int
    payment_count: int
    received_paise: int
    received_by_method: dict[str, int]


class TodayIncomeResult(BaseModel):
    rows: list[TodayIncomeRow]
    summary: TodayIncomeSummary
