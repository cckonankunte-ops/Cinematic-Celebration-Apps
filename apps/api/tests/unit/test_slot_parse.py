"""Unit tests for the legacy slot-description parser (retrofit core)."""

from __future__ import annotations

from datetime import time

import pytest

from app.services.slot_parse import ParsedSlot, parse_slot_description


@pytest.mark.parametrize(
    "text,expected",
    [
        ("9 AM - 12 PM", ParsedSlot(time(9, 0), 180)),
        ("6:30 PM - 7:30 PM", ParsedSlot(time(18, 30), 60)),
        ("10 AM - 1 PM", ParsedSlot(time(10, 0), 180)),
        ("10PM-1AM", ParsedSlot(time(22, 0), 180)),  # wraps past midnight
        ("12 PM - 2 PM", ParsedSlot(time(12, 0), 120)),  # noon
        ("12 AM - 2 AM", ParsedSlot(time(0, 0), 120)),  # midnight
        ("9 a.m. – 11 a.m.", ParsedSlot(time(9, 0), 120)),  # en-dash + dots
        ("3 PM to 4 PM", ParsedSlot(time(15, 0), 60)),  # "to" separator
    ],
)
def test_parses_known_formats(text: str, expected: ParsedSlot) -> None:
    assert parse_slot_description(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "whenever",
        "9 - 12",  # no am/pm
        "9 AM",  # no end
        "5 PM - 5 PM",  # equal -> ambiguous
        "13 PM - 2 PM",  # invalid hour
    ],
)
def test_unparseable_returns_none(text: str | None) -> None:
    assert parse_slot_description(text) is None


def test_start_minutes_are_on_half_hour_in_real_data() -> None:
    # Sanity: a :30 start parses to minute 30 (feeds the :00/:30 rule later).
    parsed = parse_slot_description("6:30 PM - 8:30 PM")
    assert parsed is not None
    assert parsed.start_time == time(18, 30)
    assert parsed.duration_minutes == 120
