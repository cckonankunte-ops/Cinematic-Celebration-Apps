"""Location (venue branch) model."""

from __future__ import annotations

from datetime import time

from sqlalchemy import Boolean, CheckConstraint, String, Text, Time, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class Location(Base, TimestampMixin):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)  # Astro route
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    # Google Maps share link shown to customers (e.g. in the WhatsApp message).
    map_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Working hours & online-booking policy (IST wall-clock) ---
    # The bookable window. closes_at may be < opens_at, meaning close is the
    # following day (e.g. opens 10:00, closes 01:00).
    opens_at: Mapped[time] = mapped_column(
        Time, nullable=False, server_default=text("'10:00'")
    )
    closes_at: Mapped[time] = mapped_column(
        Time, nullable=False, server_default=text("'01:00'")
    )
    # Latest start a customer may self-book online. Starts at/after this are only
    # offered to the public when allow_late_booking is true. Staff/admin exempt.
    last_online_booking_start: Mapped[time] = mapped_column(
        Time, nullable=False, server_default=text("'22:00'")
    )
    allow_late_booking: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # How this branch produces a booking's time window:
    #   'slot' — bookings reference a configured Slot row (slot_id); current
    #            behaviour and the default for every location.
    #   'open' — slotless; bookings carry start_time + duration_minutes directly
    #            (slot_id null). A simple admin-toggled switch (not date-scheduled)
    #            that only affects new bookings.
    booking_mode: Mapped[str] = mapped_column(
        String, nullable=False, default="slot", server_default=text("'slot'")
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "booking_mode IN ('slot', 'open')", name="ck_locations_booking_mode"
        ),
    )
