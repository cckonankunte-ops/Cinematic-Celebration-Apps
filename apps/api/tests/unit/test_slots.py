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

D = date(2026, 11, 10)  # a fixed future-ish date for the pure tests


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

NOW = datetime(2026, 11, 10, 14, 0)  # "current" IST for deterministic tests


def _validate(actor: ActorKind, start: time, duration: int, hours: LocationHours = HOURS):
    validate_booking_time(
        hours=hours,
        booking_date=D,
        start=start,
        duration_minutes=duration,
        actor=actor,
        now=NOW,
    )


def test_future_start_blocks_public_and_staff() -> None:
    for actor in (ActorKind.PUBLIC, ActorKind.STAFF):
        with pytest.raises(StartInPastError):
            _validate(actor, time(13, 0), 60)  # before NOW 14:00


def test_admin_may_book_in_the_past() -> None:
    _validate(ActorKind.ADMIN, time(13, 0), 60)  # no raise


def test_outside_working_hours_blocks_all() -> None:
    for actor in (ActorKind.PUBLIC, ActorKind.STAFF, ActorKind.ADMIN):
        with pytest.raises(OutsideWorkingHoursError):
            _validate(actor, time(2, 0), 60)  # 02:00 outside 10:00-01:00


def test_end_after_close_blocks_non_admin() -> None:
    # start 00:00 + 120 = 02:00 > close 01:00
    for actor in (ActorKind.PUBLIC, ActorKind.STAFF):
        with pytest.raises(BookingEndsAfterCloseError):
            _validate(actor, time(0, 0), 120)


def test_end_after_close_admin_override() -> None:
    _validate(ActorKind.ADMIN, time(0, 0), 120)  # admin may override


def test_end_exactly_at_close_allowed() -> None:
    _validate(ActorKind.STAFF, time(0, 0), 60)  # 00:00 + 60 = 01:00 == close


def test_late_cutoff_blocks_public_when_off() -> None:
    with pytest.raises(LateBookingDisabledError):
        _validate(ActorKind.PUBLIC, time(22, 30), 60)  # >= 22:00 cutoff, ends 23:30


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
