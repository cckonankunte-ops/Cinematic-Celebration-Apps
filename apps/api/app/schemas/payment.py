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
    amount_paise: int  # negative for a Reversing_Entry
    received_at: datetime
    recorded_by_user_id: int | None
    provider: str | None
    provider_ref: str | None
    note: str | None
    reverses_payment_id: int | None  # set on a Reversing_Entry -> original id
    is_voided: bool  # derived: True when some row reverses this one
    voided_by_payment_id: int | None  # derived: the Reversing_Entry's id, if any


class PaymentVoidRequest(BaseModel):
    """Body for the void endpoint; a blank/missing reason -> 422."""

    reason: str = Field(min_length=1)


class DerivedAmounts(BaseModel):
    total_paise: int
    amount_paid_paise: int
    amount_due_paise: int  # may be negative = overpaid
    is_paid: bool
