"""Admin advance-rule schemas (admin-only, per-location).

A rule maps a minimum booking total to the advance payable. Pricing picks the
highest matching threshold; thresholds are unique per location.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdvanceRuleCreate(BaseModel):
    min_total_paise: int = Field(ge=0)
    advance_paise: int = Field(ge=0)
    is_active: bool = True


class AdvanceRuleRead(BaseModel):
    id: int
    location_id: int
    min_total_paise: int
    advance_paise: int
    is_active: bool
