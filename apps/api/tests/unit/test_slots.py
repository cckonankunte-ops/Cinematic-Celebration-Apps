"""Unit tests for the time-range slot helpers and booking-time rule pipeline.

Pure functions, no DB. Covers: start-minute validation, occupied window + buffer,
midnight crossover, working-hours containment, and each rule in the pipeline
(future-start, working-hours, end-before-close, late-cutoff) with role
exemptions.
"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from app.core.errors import (
    BookingEndsAfterCloseError,
    LateBookingDisabledError,
    OutsideWorkingHoursError,
    StartInPastError,
)
from app.services.slots import (
    ActorKind,
    LocationHours,
    actor_kind_from_role,
    is_valid_start_minute,
    occupied_window,
    usable_end,
    validate_booking_time,
    window_fits_working_hours,
)
from app.services.slots import DisallowedRange, is_time_disallowed

D = date(2026, 11, 10)  # a fixed future-ish date for the pure tests


# --- disallowed-time ranges (R10) truth table ----------------------------
def test_is_time_disallowed_overlap_and_duration_rule() -> None:
    # Range blocks any booking overlapping 22:00-23:59 (no duration cap).
    any_dur = [DisallowedRange(start=time(22, 0), end=time(23, 59))]
    assert is_time_disallowed(any_dur, time(22, 0), 60) is True   # inside
    assert is_time_disallowed(any_dur, time(21, 30), 60) is True  # overlaps start
    assert is_time_disallowed(any_dur, time(20, 0), 60) is False  # ends 21:00, before
    assert is_time_disallowed(any_dur, time(23, 59), 60) is False  # starts at end (half-open)

    # Duration-capped range: "no bookings of <=60 min after 22:00".
    capped = [DisallowedRange(start=time(22, 0), end=time(23, 59), max_duration_minutes=60)]
    assert is_time_disallowed(capped, time(22, 0), 60) is True    # 60 <= 60 -> applies
    assert is_time_disallowed(capped, time(22, 0), 120) is False  # 120 > 60 -> does not apply
    assert is_time_disallowed(capped, time(22, 0), 30) is True    # 30 <= 60 -> applies

    # Empty ranges -> never disallowed.
    assert is_time_disallowed([], time(22, 0), 60) is False

    # Multiple ranges: disallowed if ANY applicable range overlaps.
    multi = [
        DisallowedRange(start=time(0, 0), end=time(1, 0)),
        DisallowedRange(start=time(22, 0), end=time(23, 0)),
    ]
    assert is_time_disallowed(multi, time(22, 30), 60) is True
    assert is_time_disallowed(multi, time(12, 0), 60) is False


# --- start-minute validation ---------------------------------------------
@pytest.mark.parametrize(
    "t,ok",
    [
        (time(15, 0), True),
        (time(15, 30), True),
        (time(15, 15), False),
        (time(15, 45), False),
        (time(15, 0, 30), False),
    ],
)
def test_is_valid_start_minute(t: time, ok: bool) -> None:
    assert is_valid_start_minute(t) is ok


# --- actor mapping --------------------------------------------------------
def test_actor_kind_from_role() -> None:
    assert actor_kind_from_role("admin") is ActorKind.ADMIN
    assert actor_kind_from_role("staff") is ActorKind.STAFF
    assert actor_kind_from_role(None) is ActorKind.PUBLIC
    assert actor_kind_from_role("unknown") is ActorKind.PUBLIC


# --- occupied window + buffer + midnight ----------------------------------
def test_occupied_window_includes_buffer() -> None:
    w = occupied_window(D, time(15, 0), 60, 30)
    assert w.start == datetime(2026, 11, 10, 15, 0)
    assert w.end == datetime(2026, 11, 10, 16, 30)  # 60 + 30 buffer


def test_occupied_window_crosses_midnight() -> None:
    w = occupied_window(D, time(23, 30), 120, 30)
    assert w.start == datetime(2026, 11, 10, 23, 30)
    assert w.end == datetime(2026, 11, 11, 2, 0)  # 150 min later, next day


def test_back_to_back_at_buffer_boundary_do_not_overlap() -> None:
    a = occupied_window(D, time(15, 0), 60, 30)  # [15:00, 16:30)
    b = occupied_window(D, time(16, 30), 60, 30)  # [16:30, 18:00)
    assert not a.overlaps(b)
    assert not b.overlaps(a)


def test_inside_buffer_overlaps() -> None:
    a = occupied_window(D, time(15, 0), 60, 30)  # [15:00, 16:30)
    b = occupied_window(D, time(16, 0), 60, 30)  # [16:00, 17:30)
    assert a.overlaps(b)


def test_usable_end_excludes_buffer() -> None:
    assert usable_end(D, time(15, 0), 60) == datetime(2026, 11, 10, 16, 0)


# --- working-hours containment (incl. midnight) ---------------------------
def test_window_fits_working_hours_within() -> None:
    # open 10:00 close 01:00 (next day)
    assert window_fits_working_hours(D, time(23, 30), 60, time(10, 0), time(1, 0))


def test_window_fits_working_hours_outside() -> None:
    assert not window_fits_working_hours(D, time(2, 0), 60, time(10, 0), time(1, 0))


# --- the rule pipeline ----------------------------------------------------
HOURS = LocationHours(
    opens_at=time(10, 0),
    closes_at=time(1, 0),  # closes 1 AM next day
    last_online_booking_start=time(22, 0),
    allow_late_booking=False,
)

# A "now" at the very start of D so every same-day start sorts as future (so the
# future-start rule passes and the working-hours / end-close rules are exercised).
MIDNIGHT = datetime(2026, 11, 10, 0, 0)
# A "now" mid-afternoon used only for the future-start test (13:00 is past).
AFTERNOON = datetime(2026, 11, 10, 14, 0)


def _validate(
    actor: ActorKind,
    start: time,
    duration: int,
    hours: LocationHours = HOURS,
    now: datetime = MIDNIGHT,
    staff_edit_grace_minutes: int = 0,
):
    validate_booking_time(
        hours=hours,
        booking_date=D,
        start=start,
        duration_minutes=duration,
        actor=actor,
        now=now,
        staff_edit_grace_minutes=staff_edit_grace_minutes,
    )


def test_future_start_blocks_public_and_staff_by_default() -> None:
    # Default grace = 0: both public and staff are strictly future.
    for actor in (ActorKind.PUBLIC, ActorKind.STAFF):
        with pytest.raises(StartInPastError):
            _validate(actor, time(13, 0), 60, now=AFTERNOON)  # 13:00 < 14:00


def test_staff_grace_never_applies_to_public() -> None:
    # Even with a grace window configured, PUBLIC is always strictly future.
    with pytest.raises(StartInPastError):
        _validate(
            ActorKind.PUBLIC,
            time(12, 0),
            60,
            now=datetime(2026, 11, 10, 13, 45),
            staff_edit_grace_minutes=60,
        )


def test_staff_allowed_during_running_slot_with_grace() -> None:
    # Slot 12:00-13:00, now 12:30 (in progress), grace 60 -> staff may edit.
    _validate(
        ActorKind.STAFF,
        time(12, 0),
        60,
        now=datetime(2026, 11, 10, 12, 30),
        staff_edit_grace_minutes=60,
    )


def test_staff_allowed_within_grace_after_slot() -> None:
    # Slot 12:00-13:00; usable end 13:00, +60min grace -> editable until 14:00.
    # now 13:45 is within grace -> allowed.
    _validate(
        ActorKind.STAFF,
        time(12, 0),
        60,
        now=datetime(2026, 11, 10, 13, 45),
        staff_edit_grace_minutes=60,
    )


def test_staff_blocked_after_grace() -> None:
    # now 14:30 is past the grace end (14:00) -> blocked even with grace.
    with pytest.raises(StartInPastError):
        _validate(
            ActorKind.STAFF,
            time(12, 0),
            60,
            now=datetime(2026, 11, 10, 14, 30),
            staff_edit_grace_minutes=60,
        )


def test_staff_grace_boundary_exact() -> None:
    # Exactly at grace end (14:00) is allowed; one minute past is blocked.
    _validate(
        ActorKind.STAFF,
        time(12, 0),
        60,
        now=datetime(2026, 11, 10, 14, 0),
        staff_edit_grace_minutes=60,
    )
    with pytest.raises(StartInPastError):
        _validate(
            ActorKind.STAFF,
            time(12, 0),
            60,
            now=datetime(2026, 11, 10, 14, 1),
            staff_edit_grace_minutes=60,
        )


def test_admin_may_book_in_the_past() -> None:
    _validate(ActorKind.ADMIN, time(13, 0), 60, now=AFTERNOON)  # no raise


def test_outside_working_hours_blocks_all() -> None:
    # 02:00 start is after close (01:00) and before open (10:00) -> outside.
    # now=02:00 so future-start passes for non-admins and we reach working-hours.
    for actor in (ActorKind.PUBLIC, ActorKind.STAFF, ActorKind.ADMIN):
        with pytest.raises(OutsideWorkingHoursError):
            _validate(actor, time(2, 0), 60, now=datetime(2026, 11, 10, 1, 0))


def test_end_after_close_blocks_non_admin() -> None:
    # start 00:00 + 120 = 02:00 > close 01:00; now before 00:00 so start is future.
    for actor in (ActorKind.PUBLIC, ActorKind.STAFF):
        with pytest.raises(BookingEndsAfterCloseError):
            _validate(
                actor, time(0, 0), 120, now=datetime(2026, 11, 9, 23, 0)
            )


def test_end_after_close_admin_override() -> None:
    _validate(ActorKind.ADMIN, time(0, 0), 120)  # admin may override


def test_end_exactly_at_close_allowed() -> None:
    # 00:00 + 60 = 01:00 == close; now before 00:00 so start is future.
    _validate(ActorKind.STAFF, time(0, 0), 60, now=datetime(2026, 11, 9, 23, 0))


def test_late_cutoff_blocks_public_same_day_when_off() -> None:
    # now is same-day (D); a late same-day start is blocked for public.
    with pytest.raises(LateBookingDisabledError):
        _validate(ActorKind.PUBLIC, time(22, 30), 60)  # >= 22:00 cutoff, ends 23:30


def test_late_cutoff_allows_public_future_date_when_off() -> None:
    # Same late slot, but booked for a FUTURE date: the cutoff must NOT apply.
    # now is the day before D, so D is a future booking date.
    _validate(
        ActorKind.PUBLIC, time(22, 30), 60, now=datetime(2026, 11, 9, 23, 0)
    )


def test_late_cutoff_allows_staff_and_admin() -> None:
    _validate(ActorKind.STAFF, time(22, 30), 60)
    _validate(ActorKind.ADMIN, time(22, 30), 60)


def test_late_cutoff_allows_public_when_on() -> None:
    hours = LocationHours(
        opens_at=time(10, 0),
        closes_at=time(1, 0),
        last_online_booking_start=time(22, 0),
        allow_late_booking=True,
    )
    _validate(ActorKind.PUBLIC, time(22, 30), 60, hours)  # ends 23:30 <= close
