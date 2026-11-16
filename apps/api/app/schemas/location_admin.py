"""Admin disallowed-booking-time schemas (admin-only, per-location).

Each range blocks a wall-clock (IST) window; an optional max_duration_minutes
limits the block to short bookings. The schema enforces start < end.
"""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel, Field, model_validator


class DisallowedTimeCreate(BaseModel):
    start_time: time
    end_time: time
    max_duration_minutes: int | None = Field(default=None, gt=0)
    note: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _check_order(self) -> "DisallowedTimeCreate":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class DisallowedTimeRead(BaseModel):
    id: int
    location_id: int
    start_time: time
    end_time: time
    max_duration_minutes: int | None
    note: str | None
    is_active: bool
