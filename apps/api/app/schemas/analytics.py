"""Daily analytics schemas (admin-only).

All money stays in integer paise. ``amount_due_paise`` may be negative to
represent overpayment (mirrors ``DerivedAmounts`` in the payments schema).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SlotAmountRow(BaseModel):
    booking_name: str
    booking_reference: str
    total_paise: int
    amount_paid_paise: int
    today_income_paise: int
    amount_due_paise: int  # may be negative = overpaid
    discount_paise: int
    food_paise: int
    cleaning_paise: int
    other_paise: int
    created_at: datetime


class AdvanceAmountRow(BaseModel):
    booking_name: str
    booking_reference: str
    total_paise: int
    amount_paid_paise: int
    created_at: datetime


class AnalyticsDaySummary(BaseModel):
    total_paise: int
    amount_paid_paise: int
    amount_due_paise: int
    discount_paise: int
    food_paise: int
    cleaning_paise: int
    other_paise: int


class SlotAmountsResult(BaseModel):
    rows: list[SlotAmountRow]
    summary: AnalyticsDaySummary


class AdvanceAmountsResult(BaseModel):
    rows: list[AdvanceAmountRow]
    summary: AnalyticsDaySummary
