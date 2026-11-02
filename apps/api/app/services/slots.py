"""Time-range slot helpers and the booking-time rule pipeline.

Pure, dependency-light functions over slot/location times so they can be unit
tested without a database. All times are IST wall-clock (``Asia/Kolkata``);
dates are plain calendar dates. Money/pricing is elsewhere.

The occupied window a booking blocks is
``[anchor, anchor + duration_minutes + cleaning_buffer_minutes)`` where
``anchor = booking_date + start_time`` as an IST timestamp. Anchoring on a full
timestamp makes midnight crossover automatic (e.g. 23:30 + 150 min = 02:00 next
day) and keeps overlap math correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from app.core.errors import (
    BookingEndsAfterCloseError,
    LateBookingDisabledError,
    OutsideWorkingHoursError,
    StartInPastError,
)

IST = ZoneInfo("Asia/Kolkata")

# Allowed start-time minute marks (on the hour / half-hour only).
_ALLOWED_START_MINUTES = (0, 30)


class ActorKind(str, Enum):
    """Who is booking — drives which time rules apply."""

    PUBLIC = "public"  # customer self-service (most restricted)
    STAFF = "staff"
    ADMIN = "admin"  # exempt from future-start, late-cutoff, end-before-close


def actor_kind_from_role(role: str | None) -> ActorKind:
    """Map a CurrentUser.role (or None for public) to an ActorKind."""
    if role == "admin":
        return ActorKind.ADMIN
    if role == "staff":
        return ActorKind.STAFF
    return ActorKind.PUBLIC


def is_valid_start_minute(start: time) -> bool:
    """True when the start time is on the hour or half-hour with zero seconds."""
    return start.minute in _ALLOWED_START_MINUTES and start.second == 0 and start.microsecond == 0


def now_ist() -> datetime:
    """Current time in IST (naive wall-clock, matching stored local times)."""
    return datetime.now(IST).replace(tzinfo=None)


def _anchor(on: date, start: time) -> datetime:
    """Naive IST timestamp for a slot start on a given date."""
    return datetime.combine(on, start)


def usable_end(on: date, start: time, duration_minutes: int) -> datetime:
    """End of the *usable* window (no cleaning buffer), as an IST timestamp."""
    return _anchor(on, start) + timedelta(minutes=duration_minutes)


def occupied_end(
    on: date, start: time, duration_minutes: int, cleaning_buffer_minutes: int
) -> datetime:
    """End of the *occupied* window (usable + cleaning buffer)."""
    return _anchor(on, start) + timedelta(
        minutes=duration_minutes + cleaning_buffer_minutes
    )


@dataclass(frozen=True)
class OccupiedWindow:
    """Half-open occupied range [start, end) as IST timestamps."""

    start: datetime
    end: datetime

    def overlaps(self, other: OccupiedWindow) -> bool:
        """True when the two half-open ranges intersect."""
        return self.start < other.end and other.start < self.end


def occupied_window(
    on: date, start: time, duration_minutes: int, cleaning_buffer_minutes: int
) -> OccupiedWindow:
    """Build the occupied window a booking blocks for overlap checks."""
    return OccupiedWindow(
        start=_anchor(on, start),
        end=occupied_end(on, start, duration_minutes, cleaning_buffer_minutes),
    )


def working_window(on: date, opens_at: time, closes_at: time) -> tuple[datetime, datetime]:
    """The location's open/close window on a date as IST timestamps.

    When ``closes_at <= opens_at`` the close is interpreted as the following day
    (e.g. opens 10:00, closes 01:00).
    """
    open_dt = _anchor(on, opens_at)
    close_dt = _anchor(on, closes_at)
    if closes_at <= opens_at:
        close_dt += timedelta(days=1)
    return open_dt, close_dt


def window_fits_working_hours(
    on: date, start: time, duration_minutes: int, opens_at: time, closes_at: time
) -> bool:
    """True when the usable window fits within the location's working window."""
    open_dt, close_dt = working_window(on, opens_at, closes_at)
    start_dt = _anchor(on, start)
    # A late start (e.g. 00:30) belongs to the same working window that opened
    # the previous calendar day; shift it forward a day if it sorts before open.
    if start_dt < open_dt:
        start_dt += timedelta(days=1)
    # Containment is START-only: the start must fall within [open, close). The
    # usable END exceeding close is a separate, role-aware rule (end-before-close)
    # so admins can book a late slot that runs a bit past close.
    return open_dt <= start_dt < close_dt


def full_window_within_working_hours(
    on: date, start: time, duration_minutes: int, opens_at: time, closes_at: time
) -> bool:
    """True when BOTH the start and the usable end fall within working hours.

    Used for slot-catalog validation (a configured slot should fit entirely);
    the booking pipeline uses the start-only ``window_fits_working_hours`` plus
    the role-aware end-before-close rule instead.
    """
    open_dt, close_dt = working_window(on, opens_at, closes_at)
    start_dt = _anchor(on, start)
    end_dt = usable_end(on, start, duration_minutes)
    if start_dt < open_dt:
        start_dt += timedelta(days=1)
        end_dt += timedelta(days=1)
    return open_dt <= start_dt and end_dt <= close_dt


@dataclass(frozen=True)
class LocationHours:
    """The subset of a location's config the rule pipeline needs."""

    opens_at: time
    closes_at: time
    last_online_booking_start: time
    allow_late_booking: bool


def validate_booking_time(
    *,
    hours: LocationHours,
    booking_date: date,
    start: time,
    duration_minutes: int,
    actor: ActorKind,
    now: datetime | None = None,
) -> None:
    """Validate a prospective booking's time against all time rules.

    Rules run in order and raise the first failure:
      1. future-start   — PUBLIC/STAFF only (ADMIN may book the past)
      2. working-hours  — all actors (usable window within open/close)
      3. end-before-close — PUBLIC/STAFF (ADMIN may override)
      4. late-cutoff    — PUBLIC only (STAFF/ADMIN exempt)

    Overlap/buffer conflict is checked separately (service + DB), not here.
    Raises the specific AppError; returns None when valid.
    """
    current = now if now is not None else now_ist()
    start_dt = _anchor(booking_date, start)

    # 1. Future-start (admins exempt).
    if actor is not ActorKind.ADMIN and start_dt <= current:
        raise StartInPastError()

    # 2. Working-hours containment (all actors).
    if not window_fits_working_hours(
        booking_date, start, duration_minutes, hours.opens_at, hours.closes_at
    ):
        raise OutsideWorkingHoursError()

    # 3. End-before-close for non-admins (admins may override).
    if actor is not ActorKind.ADMIN:
        _open_dt, close_dt = working_window(
            booking_date, hours.opens_at, hours.closes_at
        )
        end_dt = usable_end(booking_date, start, duration_minutes)
        if start_dt < _open_dt:
            end_dt += timedelta(days=1)
        if end_dt > close_dt:
            raise BookingEndsAfterCloseError()

    # 4. Late-booking cutoff (public self-service only).
    if actor is ActorKind.PUBLIC and not hours.allow_late_booking:
        if start >= hours.last_online_booking_start:
            raise LateBookingDisabledError()
