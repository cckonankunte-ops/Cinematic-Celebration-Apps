"""Payment ledger schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    method: Literal["cash", "upi", "card", "other"]
    amount_paise: int = Field(gt=0)
    received_at: datetime | None = None
    note: str | None = None


class PaymentRead(BaseModel):
    id: int
    booking_id: int
    method: str
    amount_paise: int
    received_at: datetime
    recorded_by_user_id: int | None
    provider: str | None
    provider_ref: str | None
    note: str | None


class DerivedAmounts(BaseModel):
    total_paise: int
    amount_paid_paise: int
    amount_due_paise: int  # may be negative = overpaid
    is_paid: bool
