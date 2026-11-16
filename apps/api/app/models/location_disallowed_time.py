"""Per-branch disallowed booking-time ranges.

Each row blocks a wall-clock (IST) range for a location. When
``max_duration_minutes`` is set the range only blocks bookings of that duration
or shorter (e.g. "no 1-hour bookings after 22:00"); NULL blocks any booking
whose occupied window overlaps the range. Config is forward-looking — it only
affects availability/creation, never existing bookings.
"""

from __future__ import annotations

from datetime import time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    SmallInteger,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class LocationDisallowedTime(Base, TimestampMixin):
    __tablename__ = "location_disallowed_times"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    # When set, only bookings of this duration or shorter are blocked; NULL
    # blocks any overlapping booking regardless of duration.
    max_duration_minutes: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    # location_id is already indexed via index=True on the column above.
    __table_args__ = (
        CheckConstraint(
            "start_time < end_time", name="ck_location_disallowed_times_order"
        ),
    )
