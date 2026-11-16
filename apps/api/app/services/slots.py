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


# How long after a slot's usable end STAFF may still edit/act on a booking.
# Lets on-floor staff update add-ons (party popper, food, etc.) during and just
# after a running slot without re-opening the whole future-start rule. PUBLIC is
# never granted this; ADMIN is fully exempt from future-start regardless.
STAFF_EDIT_GRACE_MINUTES = 60


@dataclass(frozen=True)
class DisallowedRange:
    """An active disallowed wall-clock range for a branch.

    ``max_duration_minutes`` None blocks any overlapping booking; when set, only
    bookings of that duration or shorter are blocked. Times are IST wall-clock
    on the booking date.
    """

    start: time
    end: time
    max_duration_minutes: int | None = None


def is_time_disallowed(
    ranges: list[DisallowedRange], start: time, duration_minutes: int
) -> bool:
    """True when the booking's usable window overlaps an applicable disallowed
    range.

    For each active range: the range applies only if its ``max_duration_minutes``
    is None (blocks any duration) or ``duration_minutes <= max_duration_minutes``
    (blocks short bookings, e.g. "no 1-hour bookings after 22:00"). An applicable
    range blocks when the booking's usable window
    ``[start, start + duration_minutes)`` overlaps the range ``[start, end)``.

    Pure function over wall-clock times (same-day, no midnight crossover for the
    range itself, which the admin schema guarantees via ``start < end``). The
    booking window is evaluated on a nominal date so overlap math is simple.
    """
    nominal = date(2000, 1, 1)
    book_start = datetime.combine(nominal, start)
    book_end = book_start + timedelta(minutes=duration_minutes)
    for r in ranges:
        applies = (
            r.max_duration_minutes is None
            or duration_minutes <= r.max_duration_minutes
        )
        if not applies:
            continue
        range_start = datetime.combine(nominal, r.start)
        range_end = datetime.combine(nominal, r.end)
        # Half-open overlap: [book_start, book_end) ∩ [range_start, range_end).
        if book_start < range_end and range_start < book_end:
            return True
    return False


def validate_booking_time(
    *,
    hours: LocationHours,
    booking_date: date,
    start: time,
    duration_minutes: int,
    actor: ActorKind,
    now: datetime | None = None,
    staff_edit_grace_minutes: int = 0,
) -> None:
    """Validate a prospective booking's time against all time rules.

    Rules run in order and raise the first failure:
      1. future-start   — PUBLIC only strictly; STAFF get a grace window (may act
                          until the slot's usable end + ``staff_edit_grace_minutes``);
                          ADMIN fully exempt (may book/edit the past)
      2. working-hours  — all actors (usable window within open/close)
      3. end-before-close — PUBLIC/STAFF (ADMIN may override)
      4. late-cutoff    — PUBLIC only, SAME-DAY only (STAFF/ADMIN exempt;
                          future-dated bookings always allowed)

    Overlap/buffer conflict is checked separately (service + DB), not here.
    Raises the specific AppError; returns None when valid.
    """
    current = now if now is not None else now_ist()
    start_dt = _anchor(booking_date, start)

    # 1. Future-start.
    #    - ADMIN: fully exempt (may act on any past time).
    #    - STAFF: strictly future UNLESS a positive grace is given, in which case
    #      they may act while the slot runs and until its usable end + grace, so
    #      add-ons can be edited mid/just-after a party. grace=0 => strict.
    #    - PUBLIC: strictly future.
    if start_dt <= current and actor is not ActorKind.ADMIN:
        allowed_by_grace = False
        if actor is ActorKind.STAFF and staff_edit_grace_minutes > 0:
            grace_end = usable_end(booking_date, start, duration_minutes) + timedelta(
                minutes=staff_edit_grace_minutes
            )
            allowed_by_grace = current <= grace_end
        if not allowed_by_grace:
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

    # 4. Late-booking cutoff (public self-service only) — SAME-DAY ONLY.
    #    The cutoff exists purely to stop last-minute same-day late slots after
    #    staff have left for the night. Future-dated bookings are always allowed,
    #    so the same late slot on any later date stays bookable anytime.
    if actor is ActorKind.PUBLIC and not hours.allow_late_booking:
        if booking_date == current.date() and start >= hours.last_online_booking_start:
            raise LateBookingDisabledError()
